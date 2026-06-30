using System;
using System.Net.Http.Json;
using System.Threading.Tasks;
using AuraCore.Examples.Inference;
using Grpc.Core;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace WorkerMas;

public class InferenceServiceImpl : InferenceService.InferenceServiceBase
{
    public override Task<InferenceResponse> Infer(InferenceRequest request, ServerCallContext context)
    {
        return Task.FromResult(new InferenceResponse
        {
            Result = $"[Direct Inference] Processed: {request.Prompt}"
        });
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

        app.MapGrpcService<InferenceServiceImpl>();
        app.MapGet("/", () => "Inference Worker is running.");
        
        var lifetime = app.Services.GetRequiredService<IHostApplicationLifetime>();
        lifetime.ApplicationStarted.Register(() =>
        {
            _ = Task.Run(async () =>
            {
                try {
                    var ipcPortStr = Environment.GetEnvironmentVariable("AURAGRID_IPC_PORT");
                    var ipcToken = Environment.GetEnvironmentVariable("AURAGRID_IPC_TOKEN");
                    if (!string.IsNullOrEmpty(ipcPortStr) && int.TryParse(ipcPortStr, out int ipcPort))
                    {
                        var httpClientFactory = app.Services.GetRequiredService<System.Net.Http.IHttpClientFactory>();
                        var client = httpClientFactory.CreateClient();
                        client.DefaultRequestHeaders.Add("X-AuraGrid-IPC-Token", ipcToken);
                        
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

                        var payload = new
                        {
                            port = httpPort,
                            grpcPort = grpcPort,
                            scheme = "http",
                            serviceName = "InferenceStream",
                            ipcToken = ipcToken,
                            methods = new[] { "Infer" }
                        };

                        var endpoint = $"http://127.0.0.1:{ipcPort}/cell/service-port";
                        using var response = await client.PostAsJsonAsync(endpoint, payload);
                        response.EnsureSuccessStatusCode();
                        Console.WriteLine("Successfully registered with Grid IPC.");
                    }
                }
                catch (Exception ex) {
                    Console.WriteLine("Failed to register with Grid IPC: " + ex.Message);
                }
            });
        });

        await app.RunAsync();
    }
}
