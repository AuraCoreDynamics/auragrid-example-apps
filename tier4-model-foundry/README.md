# Tier 4: Zero-Trust Model Foundry

This example demonstrates the power of AuraGrid's **Attribute-Based Access Control (ABAC)** and **Identity Propagation** in a secure machine learning context.

## Overview

The Model Foundry simulates an LLM training and inference service where different operations require different levels of authorization:

1.  **Inference (`GetStatus`)**: Restricted via ABAC. Requires the user to have the `Project:Aura` attribute.
2.  **Training (`StartTraining`)**: Restricted via RBAC. Requires the `FoundryAdmin` role.
3.  **Critical Control (`EmergencyStop`)**: Restricted via RBAC. Requires the fabric-level `GridAdmin` role.

## Key Features

-   **Declarative ABAC**: Shows how to use `required_claim` in Python to restrict methods based on identity traits beyond simple roles.
-   **Identity Attribution**: The service automatically receives the verified `user_id` from the mTLS handshake, allowing it to log exactly *who* initiated an expensive GPU training job.
-   **Hybrid Security**: Demonstrates how RBAC and ABAC work together to provide defense-in-depth.

## Usage

1.  **Deploy the Service**:
    ```bash
    $env:PYTHONPATH="C:\projects\auracore\auragrid\src\AuraGrid.PythonSdk"
    python foundry.py
    ```

2.  **Test Access**:
    -   A user with a valid cert but no `Project:Aura` attribute will receive a `403 Forbidden` on `GetStatus`.
    -   A user with the attribute but no `FoundryAdmin` role will fail to start training.
    -   Only a `GridAdmin` can trigger the emergency stop.

## See Also
-   [**AuraGrid Security Guide**](../../auragrid/docs/security.md)
-   [**Identity Sync Scenario**](../scenarios/scenario_identity_sync.py) (shows how to provision these attributes)
