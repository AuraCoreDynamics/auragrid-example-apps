# Tier 3: Secure Sovereign Ledger

## Overview
The **Sovereign Ledger** is a distributed, append-only journal service. It demonstrates the most difficult aspect of distributed computing: **Shared State, Data Integrity, and Non-Repudiation.**

## Why AuraCore? (The Difference)
Distributed locking is notoriously fragile in cloud environments, often leading to "split-brain" corruption. AuraCore solves this at the **Infrastructure Level**.
* **Native Fencing Tokens:** Every write to shared storage is protected by a hardware-verified fencing token. If a MAS loses its lease, the storage provider will reject subsequent writes.
* **Non-Repudiation (New)**: Transactions are now published to the `system.ledger` WAL topic. The AuraGrid fabric automatically signs every event with the node's private key. The included `Auditor` service can verify the chain of custody for any transaction.

## AuraCore Tech Showcased
* **Signed WAL Events:** Digitally signed audit trails with pervasive PKI verification.
* **ILeaseManager:** Distributed singleton management and lock acquisition.
* **WAL Markers:** Reporting progress during lease renewal to enable seamless failover recovery.

## Usage

1.  **Start the Ledger**:
    ```bash
    $env:PYTHONPATH="C:\projects\auracore\auragrid\src\AuraGrid.PythonSdk"
    python ledger.py
    ```

2.  **Start the Auditor**:
    ```bash
    $env:PYTHONPATH="C:\projects\auracore\auragrid\src\AuraGrid.PythonSdk"
    python auditor.py
    ```

The Auditor will display `AUDIT PASS` for every transaction, proving the fabric successfully validated the digital signatures.
