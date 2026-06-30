using System;
using System.Diagnostics;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using AuraCore.Examples.Telemetry;
using Google.Protobuf;
using Grpc.Core;
using Grpc.Net.Client;

namespace TorrentClient;

class Program
{
    static async Task Main(string[] args)
    {
        Console.WriteLine("Starting Telemetry Client...");

        var proxyUrl = Environment.GetEnvironmentVariable("AURAGRID_PROXY_URL") ?? "https://127.0.0.1:8088";
        var targetUri = new Uri($"{proxyUrl}/api/TelemetryStream/");

        Console.WriteLine($"Resolved TelemetryStream via proxy at {targetUri}. Waiting for worker readiness...");

        var targetToken = Environment.GetEnvironmentVariable("AURAGRID_IPC_TOKEN") ?? "test-token";

        // ── Readiness poll: wait up to 90s for TelemetryStream to appear in /api/services ──
        await WaitForServiceReadyAsync(proxyUrl, "TelemetryStream", TimeSpan.FromSeconds(90), targetToken);

        Console.WriteLine("Worker ready. Starting torrent...");

        var channelOptions = new GrpcChannelOptions
        {
            HttpHandler = new SubpathHandler("/api/TelemetryStream", CreateHttpMessageHandler())
        };

        using var channel = GrpcChannel.ForAddress(targetUri, channelOptions);
        var client = new TelemetryService.TelemetryServiceClient(channel);

        var headers = new Metadata { { "X-AuraGrid-IPC-Token", targetToken } };

        using var call = client.StreamData(headers);

        var cts = new CancellationTokenSource();
        long totalAcks = 0;

        var readTask = Task.Run(async () =>
        {
            try
            {
                await foreach (var ack in call.ResponseStream.ReadAllAsync(cts.Token))
                    Interlocked.Increment(ref totalAcks);
            }
            catch (OperationCanceledException) { }
        });

        // 50 MB total, 100 KB chunks
        long targetBytes = 50L * 1024 * 1024;
        int chunkSize = 100 * 1024;
        int totalChunks = (int)(targetBytes / chunkSize);

        var payloadData = new byte[chunkSize];
        new Random().NextBytes(payloadData);
        var byteString = ByteString.CopyFrom(payloadData);

        var sw = Stopwatch.StartNew();

        for (int i = 0; i < totalChunks; i++)
        {
            await call.RequestStream.WriteAsync(new DataChunk
            {
                ChunkId = i,
                Payload = byteString
            });
        }

        Console.WriteLine("Finished writing chunks. Completing stream...");
        await call.RequestStream.CompleteAsync();
        await readTask;
        sw.Stop();

        Console.WriteLine($"Torrent completed. Sent {targetBytes / 1024.0 / 1024.0:F2} MB in {sw.ElapsedMilliseconds} ms.");
        Console.WriteLine($"Received {totalAcks} ACKs. Speed: {targetBytes / 1024.0 / 1024.0 / sw.Elapsed.TotalSeconds:F2} MB/s");

        cts.Cancel();
    }

    static HttpMessageHandler CreateHttpMessageHandler()
    {
        var certPath = Environment.GetEnvironmentVariable("AURAGRID_CLIENT_CERT_PATH");
        var certPass = Environment.GetEnvironmentVariable("AURAGRID_CLIENT_CERT_PASSWORD");

        var handler = new SocketsHttpHandler
        {
            EnableMultipleHttp2Connections = true,
            KeepAlivePingDelay = TimeSpan.FromSeconds(60),
            KeepAlivePingTimeout = TimeSpan.FromSeconds(30),
            SslOptions = new System.Net.Security.SslClientAuthenticationOptions
            {
                RemoteCertificateValidationCallback = (_, _, _, _) => true
            }
        };

        if (!string.IsNullOrEmpty(certPath) && File.Exists(certPath))
        {
            try
            {
                var clientCert = new System.Security.Cryptography.X509Certificates.X509Certificate2(certPath, certPass);
                handler.SslOptions.ClientCertificates = new System.Security.Cryptography.X509Certificates.X509Certificate2Collection(clientCert);
                Console.WriteLine($"[PKI] Loaded client certificate: {clientCert.Subject}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[PKI Warning] Failed to load client certificate from {certPath}: {ex.Message}");
            }
        }
        else
        {
            Console.WriteLine("[PKI] Warning: No client certificate loaded.");
        }

        return handler;
    }

    static async Task WaitForServiceReadyAsync(string proxyUrl, string serviceName, TimeSpan timeout, string ipcToken)
    {
        using var http = new HttpClient(CreateHttpMessageHandler());
        http.DefaultRequestHeaders.Add("X-AuraGrid-IPC-Token", ipcToken);
        var deadline = DateTimeOffset.UtcNow + timeout;

        while (DateTimeOffset.UtcNow < deadline)
        {
            try
            {
                var services = await http.GetFromJsonAsync<JsonElement[]>($"{proxyUrl}/api/services");
                if (services != null && services.Any(s =>
                    s.TryGetProperty("serviceName", out var sn) &&
                    sn.GetString()?.Equals(serviceName, StringComparison.OrdinalIgnoreCase) == true))
                {
                    Console.WriteLine($"[readiness] {serviceName} found in /api/services.");
                    return;
                }
            }
            catch (Exception ex)
            {
                /* grid may not be ready yet */
            }

            Console.WriteLine($"[readiness] Waiting for {serviceName} to register...");
            await Task.Delay(TimeSpan.FromSeconds(3));
        }

        Console.WriteLine($"[readiness] WARNING: {serviceName} not found after {timeout.TotalSeconds}s. Proceeding anyway.");
    }

    private sealed class SubpathHandler : DelegatingHandler
    {
        private readonly string _subpath;

        public SubpathHandler(string subpath, HttpMessageHandler innerHandler) : base(innerHandler)
        {
            _subpath = subpath.TrimEnd('/');
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var oldPath = request.RequestUri.AbsolutePath;
            if (!oldPath.StartsWith(_subpath, StringComparison.OrdinalIgnoreCase))
            {
                var builder = new UriBuilder(request.RequestUri);
                builder.Path = _subpath + oldPath;
                request.RequestUri = builder.Uri;
            }
            return base.SendAsync(request, cancellationToken);
        }
    }
}

