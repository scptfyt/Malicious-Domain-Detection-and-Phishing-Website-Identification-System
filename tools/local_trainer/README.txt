Local Trainer Assistant
=======================

This folder contains a local Windows training assistant for the malicious domain
detection project.

Usage:
1. Extract this folder to a stable location, such as D:\DomainTrainer.
2. Run install_dependencies.cmd once to install Python packages.
3. Right click install_protocol.ps1 and choose "Run with PowerShell", or run:
   powershell -ExecutionPolicy Bypass -File install_protocol.ps1
4. Open the web system and click "Open Local Trainer".

The assistant trains models on the user's own computer and saves output files to
the selected local directory. It does not upload training files automatically.
