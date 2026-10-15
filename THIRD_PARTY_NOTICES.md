# 引用与许可

本项目自行编写的代码按 MIT 许可提供；见 LICENSE。请结合各依赖许可分发。

- DanMo661/Xuexitong-mcp（https://github.com/DanMo661/Xuexitong-mcp），MIT，copyright Wu Jiale。assistant/upstream.py 提取/适配其中辅助函数和 fetch_chapters；许可证见 licenses/Xuexitong-mcp-MIT.txt。没有采用其明文凭据持久化代码。
- Zhanghuaimin-233/chaoxing-homework-checker（https://github.com/Zhanghuaimin-233/chaoxing-homework-checker），GPL-3.0。仅作为网页协议、状态文本和分页研究参考，未发布其研究快照，参考许可文本见 licenses/homework-checker-GPL-3.0.txt；没有将其用户脚本打包进应用。独立 Python 网络适配器未复制其 JS 实现。
- mshzy/study_assistant（https://github.com/mshzy/study_assistant），MIT，copyright HY。仅研究，未复制其 Dart 实现；许可见 licenses/study_assistant-MIT.txt。
- PySide6 / Qt：按发行包所附 LGPL/GPL/其他组件许可，动态链接 DLL，许可证收录于 licenses/dependencies 下；Qt 源码可从 https://code.qt.io/ 获取，对应本次 Qt 6.12.0。用户可替换兼容动态库，适用开源许可允许为修改库调试进行逆向工程。构建/替换时须保留兼容 ABI 和全部 WebEngine 资源。
- QtWebEngine 包含 Chromium 及第三方组件。对应上游来源 https://code.qt.io/cgit/qt/qtwebengine.git/ 。请保留发行包的第三方许可与资源。
- requests（Apache-2.0）、Beautiful Soup（MIT）、PyCryptodome（BSD/public domain）、SQLite（public domain）、Python（PSF）、PyInstaller（GPL及bootloader例外）。实际安装发行包的可用许可文本归档在 licenses/dependencies。

完整依赖与版本见 requirements-lock.txt。研究资料未作为已验证的官方公开接口发布。平台自身内容、名称和标识归其权利人所有。

Windows 单文件 EXE 内置用户提供的 Geek Uninstaller 1.6.0.200，由原软件权利人保留权利，不属于本项目 MIT 许可范围。源码不包含该可执行文件；复制与打包未修改其内容或数字签名。使用方法见 docs/百宝箱.md。

内存清理参考 PCL-Community/PCL-CE 贡献者在提交 7b5c912ffa29ef5554d069e7605d3faa99238c4a 下公开的 MemSwapService/MemSwapWorks 设计与系统调用，原项目采用 Apache-2.0；许可见 licenses/PCL-CE-Apache-2.0.txt，研究说明见 docs/内存清理研究.md。本项目独立编写 Python 实现，未引入 PCL 可执行文件或 C# 源文件；与 PCL 官方没有从属关系。没有复制许可不同的 PCL 主线代码。
