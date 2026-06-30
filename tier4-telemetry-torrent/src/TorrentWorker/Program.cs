using System;
using System.Net.Http.Json;
using System.Threading.Tasks;
using AuraCore.Examples.Telemetry;
using Grpc.Core;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace TorrentWorker;

public class TelemetryServiceImpl : TelemetryService.TelemetryServiceBase
{
    private readonly ILogger<TelemetryServiceImpl> _logger;

    public TelemetryServiceImpl(ILogger<TelemetryServiceImpl> logger)
    {
        _logger = logger;
    }

    public override async Task StreamData(IAsyncStreamReader<DataChunk> requestStream, IServerStreamWriter<Ack> responseStream, ServerCallContext context)
    {
        _logger.LogInformation("Client connected. Starting unbuffered telemetry stream...");
        long totalBytes = 0;
        int chunkCount = 0;

        try
        {
            await foreach (var chunk in requestStream.ReadAllAsync(context.CancellationToken))
            {
                totalBytes += chunk.Payload.Length;
                chunkCount++;

                // Immediately yield an ack back over the unbuffered HTTP/2 stream
                await responseStream.WriteAsync(new Ack
                {
                    ChunkId = chunk.ChunkId,
                    Success = true
                });

                if (chunkCount % 100 == 0)
                {
                    _logger.LogInformation($"Received {chunkCount} chunks. Total bytes: {totalBytes / 1024.0 / 1024.0:F2} MB");
                }
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            _logger.LogError(ex, "Error during stream");
        }

        _logger.LogInformation($"Stream completed. Total chunks: {chunkCount}, Total bytes: {totalBytes / 1024.0 / 1024.0:F2} MB");
    }
}

class Program
{
    static async Task Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);
        builder.WebHost.ConfigureKestrel(options =>
        {
            options.Listen(System.Net.IPAddress.Loopback, 0, listenOptions =>
            {
                listenOptions.Protocols = Microsoft.AspNetCore.Server.Kestrel.Core.HttpProtocols.Http1;
            });
            options.Listen(System.Net.IPAddress.Loopback, 0, listenOptions =>
            {
                listenOptions.Protocols = Microsoft.AspNetCore.Server.Kestrel.Core.HttpProtocols.Http2;
            });
        });
        builder.Services.AddGrpc();
        builder.Services.AddHttpClient();
        
        var app = builder.Build();

        app.MapGrpcService<TelemetryServiceImpl>();
        app.MapGet("/", () => "Telemetry Worker is running.");
        
        var lifetime = app.Services.GetRequiredService<IHostApplicationLifetime>();
        var logger = app.Services.GetRequiredService<ILogger<Program>>();
        lifetime.ApplicationStarted.Register(() =>
        {
            _ = Task.Run(async () =>
            {
                try {
                    logger.LogInformation("TorrentWorker ApplicationStarted event triggered. Checking environment variables...");
                    foreach (System.Collections.DictionaryEntry de in Environment.GetEnvironmentVariables())
                    {
                        var key = de.Key?.ToString();
                        if (key != null && key.StartsWith("AURAGRID_", StringComparison.OrdinalIgnoreCase))
                        {
                            logger.LogInformation("Env var: {Key} = {Value}", key, de.Value);
                        }
                    }

                    var ipcPortStr = Environment.GetEnvironmentVariable("AURAGRID_IPC_PORT");
                    var ipcToken = Environment.GetEnvironmentVariable("AURAGRID_IPC_TOKEN");
                    
                    logger.LogInformation("Read env: AURAGRID_IPC_PORT={IpcPortStr}, AURAGRID_IPC_TOKEN={IpcToken}", ipcPortStr, ipcToken);
                    
                    if (string.IsNullOrEmpty(ipcPortStr))
                    {
                        logger.LogWarning("AURAGRID_IPC_PORT is null or empty! Registration aborted.");
                        return;
                    }

                    if (!int.TryParse(ipcPortStr, out int ipcPort))
                    {
                        logger.LogError("Failed to parse AURAGRID_IPC_PORT '{IpcPortStr}' to int! Registration aborted.", ipcPortStr);
                        return;
                    }

                    var httpClientFactory = app.Services.GetRequiredService<System.Net.Http.IHttpClientFactory>();
                    var client = httpClientFactory.CreateClient();
                    client.DefaultRequestHeaders.Add("X-AuraGrid-IPC-Token", ipcToken);
                    
                    // Try to parse the bound port
                    int httpPort = 5000;
                    int grpcPort = 5000;
                    var addresses = app.Services.GetRequiredService<Microsoft.AspNetCore.Hosting.Server.IServer>().Features.Get<Microsoft.AspNetCore.Hosting.Server.Features.IServerAddressesFeature>();
                    if (addresses != null)
                    {
                        var addressList = new System.Collections.Generic.List<string>(addresses.Addresses);
                        if (addressList.Count >= 2)
                        {
                            httpPort = new Uri(addressList[0]).Port;
                            grpcPort = new Uri(addressList[1]).Port;
                        }
                        else if (addressList.Count == 1)
                        {
                            httpPort = new Uri(addressList[0]).Port;
                            grpcPort = httpPort;
                        }
                    }

                    logger.LogInformation("Selected HTTP port: {HttpPort}, gRPC port: {GrpcPort} for self-registration", httpPort, grpcPort);

                    var payload = new
                    {
                        port = httpPort,
                        grpcPort = grpcPort,
                        scheme = "http",
                        serviceName = "TelemetryStream",
                        ipcToken = ipcToken,
                        methods = new[] { "StreamData" }
                    };

                    var endpoint = $"http://127.0.0.1:{ipcPort}/cell/service-port";
                    logger.LogInformation("Posting registration to {Endpoint} with payload: {Payload}", endpoint, payload);

                    using var response = await client.PostAsJsonAsync(endpoint, payload);
                    response.EnsureSuccessStatusCode();
                    logger.LogInformation("Successfully registered with Grid IPC.");
                }
                catch (Exception ex) {
                    logger.LogError(ex, "Failed to register with Grid IPC.");
                }
            });
        });

        await app.RunAsync();
    }
}
