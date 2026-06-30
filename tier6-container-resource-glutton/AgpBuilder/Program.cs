using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using AuraGrid.Abstractions.Configuration;
using AuraGrid.Abstractions.Deployment;
using AuraGrid.ProxyWorker.Deployment;
using AuraGrid.ProxyWorker.Deployment.Packaging;
using Microsoft.Extensions.Logging.Abstractions;

namespace AgpBuilder
{
    class Program
    {
        static async Task Main(string[] args)
        {
            Console.WriteLine("Starting AGP Builder...");

            // 1. Setup transpiler dependencies
            var gridRootConfig = new GridRootConfiguration { RootPath = "C:/GridRoot" };
            var logger = NullLogger<ContainerTranspiler>.Instance;
            
            // 2. We use reflection since ContainerTranspiler is internal
            var assembly = typeof(AgpPackageFormat).Assembly;
            var transpilerType = assembly.GetType("AuraGrid.ProxyWorker.Deployment.ContainerTranspiler");
            var transpiler = Activator.CreateInstance(transpilerType, gridRootConfig, logger);

            var descriptorType = assembly.GetType("AuraGrid.ProxyWorker.Deployment.ContainerDescriptor");
            var serviceDescriptorType = assembly.GetType("AuraGrid.ProxyWorker.Deployment.ContainerServiceDescriptor");

            var descriptor = Activator.CreateInstance(descriptorType);
            
            var svc1 = Activator.CreateInstance(serviceDescriptorType);
            serviceDescriptorType.GetProperty("Name").SetValue(svc1, "glutton");
            serviceDescriptorType.GetProperty("Image").SetValue(svc1, "tier6-glutton:latest");
            serviceDescriptorType.GetProperty("Volumes").SetValue(svc1, new Dictionary<string, string> {
                { "./data", "/data" }
            });

            var servicesList = descriptorType.GetProperty("Services").GetValue(descriptor);
            servicesList.GetType().GetMethod("Add").Invoke(servicesList, new[] { svc1 });

            // 3. Transpile
            var transpileMethod = transpilerType.GetMethod("Transpile");
            var version = new Version(1, 0, 0);
            var manifest = transpileMethod.Invoke(transpiler, new object[] {
                "tier6-container-resource-glutton",
                "Tier 6 Resource Glutton",
                version,
                descriptor
            });

            // 4. Save manifest to a staging directory
            var stagingDir = Path.Combine(Directory.GetCurrentDirectory(), "staging");
            if (Directory.Exists(stagingDir)) Directory.Delete(stagingDir, true);
            Directory.CreateDirectory(stagingDir);

            var options = new JsonSerializerOptions { WriteIndented = true, PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
            var json = JsonSerializer.Serialize(manifest, options);
            
            var manifestPath = Path.Combine(stagingDir, "app.manifest.json");
            await File.WriteAllTextAsync(manifestPath, json);
            Console.WriteLine("Manifest written:\n" + json);

            // Create empty SBOM for packaging to succeed if required
            var sbomContent = @"{ ""components"": [] }";
            await File.WriteAllTextAsync(Path.Combine(stagingDir, "sbom.json"), sbomContent);

            // 5. Build .agp package
            var outAgp = Path.Combine(Directory.GetCurrentDirectory(), "..", "tier6-container-resource-glutton-1.0.0.agp");
            if (File.Exists(outAgp)) File.Delete(outAgp);
            
            await AgpPackageBuilder.BuildAsync(stagingDir, outAgp);
            Console.WriteLine($"Successfully built AGP package at: {outAgp}");
        }
    }
}
