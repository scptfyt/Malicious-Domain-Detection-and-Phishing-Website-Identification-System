本地训练助手 / Local Trainer Assistant
====================================

中文说明
--------

本目录提供恶意域名检测与钓鱼网站识别系统的本地训练助手。训练过程在用户自己的电脑上完成，模型文件会保存到用户选择的本地目录，不会自动上传训练数据。

推荐安装方式：
1. 将 local-trainer.zip 解压到稳定目录，例如 D:\DomainTrainer。
2. 双击 install_all.cmd，一次性完成 Python 依赖安装和 domaintrainer:// 本地协议注册。
3. 回到网页系统，点击“打开本地训练助手”。
4. 在本地训练助手中选择正常样本文件、恶意/钓鱼样本文件、模型类型和输出目录，然后开始训练。
5. 训练完成后，在本地目录查看模型文件和指标文件，并在网页系统中导入。

单独维护方式：
- install_dependencies.cmd 只安装训练所需依赖。
- install_protocol.cmd 只注册 domaintrainer:// 本地协议。
- 当一键安装失败时，可以分别运行上述两个脚本定位问题。

日志位置：
- 一键安装日志：%LOCALAPPDATA%\DomainTrainer\install_all.log
- 协议注册日志：%LOCALAPPDATA%\DomainTrainer\protocol_install.log
- 启动日志：%LOCALAPPDATA%\DomainTrainer\trainer_launch.log
- 命令行启动日志：%LOCALAPPDATA%\DomainTrainer\trainer_cmd.log

如果点击网页按钮后没有打开程序：
- 确认已经解压压缩包，而不是直接在压缩包内运行脚本。
- 重新运行 install_all.cmd。
- 确认本机已经安装 Python 3.11 或更高版本。
- 双击 open_trainer.cmd 直接启动，并查看上述日志文件。

English
-------

This folder contains the local training assistant for the malicious domain
detection and phishing website identification system. Training runs on the
user's own computer. Model files are saved to the selected local directory, and
training data is not uploaded automatically.

Recommended setup:
1. Extract local-trainer.zip to a stable directory, for example D:\DomainTrainer.
2. Double-click install_all.cmd to install Python dependencies and register the
   domaintrainer:// local protocol in one step.
3. Return to the web system and click "Open Local Trainer".
4. In the local assistant, choose benign sample file, malicious/phishing sample
   file, model type, and output directory, then start training.
5. After training, import the generated model file and metrics file in the web
   system.

Separate maintenance scripts:
- install_dependencies.cmd installs only the required training dependencies.
- install_protocol.cmd registers only the domaintrainer:// local protocol.
- If the one-step installer fails, run these two scripts separately to locate
  the problem.

Log files:
- Full installation log: %LOCALAPPDATA%\DomainTrainer\install_all.log
- Protocol registration log: %LOCALAPPDATA%\DomainTrainer\protocol_install.log
- Launch log: %LOCALAPPDATA%\DomainTrainer\trainer_launch.log
- Command launch log: %LOCALAPPDATA%\DomainTrainer\trainer_cmd.log

If the web button does not open the assistant:
- Make sure the package has been extracted first.
- Run install_all.cmd again.
- Make sure Python 3.11 or later is installed.
- Double-click open_trainer.cmd directly and check the log files listed above.
