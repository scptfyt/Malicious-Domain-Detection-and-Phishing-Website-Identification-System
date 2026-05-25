本地训练助手 / Local Trainer Assistant
====================================

中文说明
--------

本目录提供“恶意域名检测与钓鱼网站识别系统”的本地训练助手。训练过程在用户自己的电脑上完成，模型文件会保存到用户选择的本地目录，不会自动上传训练数据。

使用步骤：
1. 将 local-trainer.zip 解压到稳定目录，例如 D:\DomainTrainer。
2. 双击 install_dependencies.cmd，安装本地训练所需依赖。
3. 双击 install_protocol.cmd，注册 domaintrainer:// 本地协议。
   如果系统阻止脚本运行，也可以右键 install_protocol.ps1，选择“使用 PowerShell 运行”。
4. 回到网页系统，点击“打开本地训练助手”。
5. 在本地训练助手中选择正常样本文件、恶意/钓鱼样本文件、模型类型和输出目录，然后开始训练。

如果点击网页按钮后没有打开程序：
- 确认已经解压压缩包，而不是直接在压缩包内运行脚本。
- 重新运行 install_protocol.cmd。
- 确认本机已经安装 Python 3.11 或更高版本。
- 确认已经运行 install_dependencies.cmd。
- 双击 open_trainer.cmd 直接启动，如果窗口提示失败，请查看同目录下的 trainer_launch.log。

English
-------

This folder contains the local training assistant for the malicious domain
detection and phishing website identification system. Training runs on the
user's own computer. Model files are saved to the selected local directory, and
training data is not uploaded automatically.

Usage:
1. Extract local-trainer.zip to a stable directory, for example D:\DomainTrainer.
2. Double-click install_dependencies.cmd to install required Python packages.
3. Double-click install_protocol.cmd to register the domaintrainer:// protocol.
   If Windows blocks the script, right-click install_protocol.ps1 and choose
   "Run with PowerShell".
4. Return to the web system and click "Open Local Trainer".
5. In the local assistant, choose benign sample file, malicious/phishing sample
   file, model type, and output directory, then start training.

If the web button does not open the assistant:
- Make sure the package has been extracted first.
- Run install_protocol.cmd again.
- Make sure Python 3.11 or later is installed.
- Make sure install_dependencies.cmd has been run.
- Double-click open_trainer.cmd directly. If startup fails, check
  trainer_launch.log in the same folder.
