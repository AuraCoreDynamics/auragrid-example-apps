using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using AuraCore.Examples.Inference;
using Google.Protobuf;
using Grpc.Core;
using Grpc.Net.Client;

namespace OrchestratorMas;

class Program
{
    static async Task Main(string[] args)
    {
        Console.WriteLine("Starting Orchestrator MAS...");
        
        var proxyUrl = Environment.GetEnvironmentVariable("AURAGRID_PROXY_URL") ?? "https://127.0.0.1:8088";
        var targetUri = new Uri($"{proxyUrl}/api/InferenceStream/");
        
        Console.WriteLine($"Resolved InferenceStream via proxy at {targetUri}. Starting bypass inference...");

        // Connect to the proxy
        var channelOptions = new GrpcChannelOptions
        {
            HttpHandler = new SubpathHandler("/api/InferenceStream", CreateHttpMessageHandler())
        };

        using var channel = GrpcChannel.ForAddress(targetUri, channelOptions);
        var client = new InferenceService.InferenceServiceClient(channel);
        
        var targetToken = Environment.GetEnvironmentVariable("AURAGRID_IPC_TOKEN") ?? "test-token";
        var headers = new Metadata
        {
            { "X-AuraGrid-IPC-Token", targetToken }
        };

        try
        {
            var sw = Stopwatch.StartNew();
            var response = await client.InferAsync(new InferenceRequest { Prompt = "Test direct bypass" }, headers);
            sw.Stop();
            
            Console.WriteLine($"Inference Response: {response.Result}");
            Console.WriteLine($"Time taken: {sw.ElapsedMilliseconds} ms.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error during inference: {ex.Message}");
        }
    }

    static HttpMessageHandler CreateHttpMessageHandler()
    {
        var certPath = Environment.GetEnvironmentVariable("AURAGRID_CLIENT_CERT_PATH");
        var certPass = Environment.GetEnvironmentVariable("AURAGRID_CLIENT_CERT_PASSWORD");

        var handler = new SocketsHttpHandler
        {
            EnableMultipleHttp2Connections = true,
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

