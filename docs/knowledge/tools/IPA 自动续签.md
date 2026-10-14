---
title: IPA 自动续签
---
# IPA 自动续签 {#ipa-自动续签}


!!! summary "最终有效环路"
    `LiveContainer + 内置 SideStore Nightly → Shadowrocket 登录 Apple Account → 关闭 Shadowrocket → LocalDevVPN 安装/续签 → WebDAV 同步 Kazumi 数据`。


这篇笔记记录我在 iPad 上安装 Kazumi 的实际可用方案，这实际上就代表你可以通过本文的方法安装大部分的无签名IPA。

资料核对日期：2026-08-28。SideStore、LiveContainer 和 iOS 的行为变化较快，Nightly 中的修复以后可能进入 Stable，出问题时应先查最新版官方文档。

## 一、先理解整套系统 {#一先理解整套系统}

免费 Apple Account 的个人开发签名通常只有 7 天有效期，同时最多保留 3 个侧载 App。到期前重新签名即可继续使用；不续签时 App 会打不开，但并不等于它的数据立即被删除。Kazumi 的官方 iOS 教程也采用这一机制。

当然，你可以使用爱思助手等等应用来签名，但是因为我们要实现自动续签，加上其他种种原因，笔者选择了iLoader。

| 组件            | 在这套方案中的作用                                                |
| ------------- | -------------------------------------------------------- |
| Apple Account | 申请个人开发证书和 provisioning profile                           |
| iLoader       | 首次从 Mac 安装 LiveContainer + SideStore，并生成或放置 pairing file |
| pairing file  | 保存设备与开发工具之间的配对信任关系，让 SideStore 能识别并管理当前设备                |
| SideStore     | 在 iPad 上登录 Apple Account、生成签名并执行 `Refresh All`           |
| LocalDevVPN   | 建立 SideStore 需要的本地回环通道，使 iOS 能连接设备自身提供的开发服务              |
| Shadowrocket  | 在登录阶段让 `gsa.apple.com` 等 Apple 登录端点正常访问                  |
| LiveContainer | 用一个已签名的宿主运行多个访客 IPA，节省免费账号的 App 槽位                       |
| WebDAV        | 在 Mac 与 iPad 的 Kazumi 之间同步观看记录和追番数据                      |

SideStore 的本地 VPN 看起来像普通 VPN，但核心用途不同：它让设备访问一个本地开发端点。也正因为 iOS 上这些 VPN 配置会互相争用，我需要先用 Shadowrocket 完成联网登录，再切换到 LocalDevVPN 完成本地安装。

LiveContainer 则是宿主而不是模拟器。它把访客 App 加载到自身进程中，因此多个访客 App 不具备与正常 iOS App 完全相同的独立沙盒。官方也明确提示：访客 App 可能访问其他访客 App 的数据，App Extensions、远程推送以及部分 entitlement 不受支持。密码管理器、银行类应用和存有高敏感账号的 App 不应该放进去。

## 二、首次安装：我实际跑通的步骤 {#二首次安装我实际跑通的步骤}


!!! caution
    ~~实际证明，network是最大的障碍~~


### 1. 准备 {#1-准备}

- Mac 上安装最新版 [iLoader](https://github.com/nab138/iloader)。
- iPad 安装 LocalDevVPN；它在外区 App Store 更容易获得。
- 准备一个可以正常使用的 Apple Account。考虑到 LiveContainer 内置 SideStore 的密钥链隔离并非绝对安全，最好使用专门用于侧载的次要账号。
- 从官方渠道取得 LiveContainer + SideStore。我的环境在 Stable 相关流程失败后，换用 Nightly 才继续跑通
- iPad 保持 Wi-Fi 连接，并准备一根稳定的数据线用于首次配对。

### 2. 用 iLoader 安装宿主 {#2-用-iloader-安装宿主}

1. 用数据线把 iPad 连接到 Mac，解锁设备，并在两端确认“信任此电脑”。
2. 在 iLoader 中选择 `LiveContainer + SideStore Nightly`，按提示完成安装和 pairing file 放置。
3. 在 iPad 打开 `设置 → 隐私与安全性 → 开发者模式`，开启后按提示重启。
4. 打开 `设置 → 通用 → VPN 与设备管理`，信任对应 Apple Account 的开发者 App。
5. 打开 LiveContainer，通过左上角 SideStore 按钮进入内置 SideStore。

### 3. 用 Shadowrocket 完成 SideStore 登录 {#3-用-shadowrocket-完成-sidestore-登录}

输入后报错：

```text
The data couldn't be read, because it isn't in the correct format.
```

在本次环境中，这不是验证码格式错误，而是 SideStore 没有从 Apple 登录端点得到预期的数据。我的解决办法是：


!!! caution
    确认`gsa.apple`走的是代理，这很重要


### 4. 改用 LocalDevVPN 完成安装链路 {#4-改用-localdevvpn-完成安装链路}

1. 确认 Shadowrocket 已断开。
2. 打开 LocalDevVPN，点击连接，并保持 Wi-Fi 开启。
3. 再次进入 LiveContainer 的内置 SideStore。
4. 进入 `My Apps`，点击 `Refresh All`。
5. 如果出现撤销旧证书或创建新证书的提示，按当前界面提示继续。
6. 等待 SideStore 完成操作。成功标准不是“没有新错误日志”，而是 LiveContainer 的有效期恢复到约 `7 DAYS`，并且应用能够正常打开。
7. 退出 SideStore，回到 LiveContainer 的设置，点击 `Import Certificate from SideStore`。


SideStore 官方说明要求在安装、更新或刷新时保持 Wi-Fi 和 LocalDevVPN 连接。pairing file 可能在系统更新、设备重置或 Apple 随机失效后需要重新放置，但正常每周续签不需要重新配对。

### 5. 从 Source 安装 Kazumi {#5-从-source-安装-kazumi}

最终我不再通过 AirDrop 查找 IPA，而是直接使用 Kazumi Source：

```text
https://raw.githubusercontent.com/ChouChiu/Kazumi-AltStore-Source/kazumi/generated/apps.json
```

操作路径：

1. 在内置 SideStore 打开 `Sources`。
2. 点击右上角 `+`，添加上面的 Source URL。
3. 进入 Kazumi Source，选择 Kazumi 安装。
4. 安装完成后回到 LiveContainer，确认 Kazumi 已出现在访客 App 列表，并实际打开一次。



## 三、这次遇到的错误与判断顺序 {#三这次遇到的错误与判断顺序}

回环路由
```toml
[General]
compatibility-mode = 1
dns-server = system
```

当然，你可以在Health Check中看到Sidestore的健康状态--

| 错误或现象                                        | 本次环境中的含义                             | 优先处理                                                           |
| -------------------------------------------- | ------------------------------------ | -------------------------------------------------------------- |
| `The data couldn't be read...correct format` | Apple 登录端点返回异常；验证码本身不一定有错            | 用 Shadowrocket 确保 Apple 登录请求经可用代理，再重新登录                        |
| `Minimuxer.IdeviceGatewayError 0`            | SideStore 到本机开发端点的连接没有完成             | 关闭 Shadowrocket，连接 Wi-Fi 与 LocalDevVPN，重开 SideStore            |
| `Handshake failed: Connection reset by peer` | 本地握手被重置；表面上像 pairing 错误，也可能是通道没有正确建立 | 先修复 LocalDevVPN 路由，再判断 pairing file                            |
| `DeviceEndpointNotInitialized` / peer IP 不可达 | VPN 接口存在，但 SideStore 找不到可达的设备端点      | 确认当前连接的是 LocalDevVPN，而不是普通代理 VPN                               |
| `SideStore.OperationError 1006` / 无法确定 UDID  | pairing file 缺失、失效，或本地端点尚未正确工作       | 使用idevice_pair(项目在github)；仍失败时再用最新版 iLoader 重建并放置 pairing file |
| `Unable to manage profiles on the device`    | 本次刷新没有成功管理开发描述文件                     | 不把它当成成功，回到 VPN、pairing 和证书链路排查                                 |
| Error Log 中没有新条目                             | 只能说明没有写入日志，不能证明刷新完成                  | 看 `My Apps` 有效期，并实际打开 App                                      |


## 四、以后每周怎么续签 {#四以后每周怎么续签}

### 稳定的手动流程 {#稳定的手动流程}

建议在只剩 1～2 天时操作，不要等到宿主已经无法打开：

1. 断开 Shadowrocket 或其他普通代理 VPN。
2. 连接 Wi-Fi。
3. 打开并连接 LocalDevVPN。
4. 打开 LiveContainer，再进入内置 SideStore。
5. 在 `My Apps` 点击 `Refresh All`。
6. 等待有效期恢复到约 `7 DAYS`，并打开 Kazumi 验证。
7. 断开 LocalDevVPN，恢复日常使用的 Shadowrocket。

这一步是重新签名，不是删除并重新安装，因此正常情况下不会清除 Kazumi、观看记录、规则或 WebDAV 配置，也不需要 Mac 参与。

如果已经过期到 LiveContainer 无法打开，才需要重新连接 Mac，由 iLoader 恢复宿主。系统大版本更新、设备重置或持续的 `1006` 也可能要求替换 pairing file；这不是每周例行操作。

### 可选：快捷指令自动刷新 {#可选快捷指令自动刷新}

LiveContainer + SideStore 支持用于刷新的快捷指令动作，可以进一步创建个人自动化，例如连接家庭 Wi-Fi 后尝试刷新。但我尚未在这台 iPad 上验证锁屏、后台和系统升级后的可靠性，因此目前把它视为辅助方案

## 五、Kazumi 的 WebDAV 同步 {#五kazumi-的-webdav-同步}

WebDAV 与 IPA 签名是两条完全独立的链路：

```text
SideStore / LocalDevVPN：让 App 保持可打开
WebDAV：让不同设备上的 Kazumi 共享观看记录和追番数据
```

Kazumi 当前使用 WebDAV 同步追番和观看记录。观看记录可以在启用相关选项后自动同步；追番同步的自动化程度可能随版本变化，跨设备切换前手动同步一次最稳妥。WebDAV 不会同步 IPA、签名证书、pairing file，也不会把 WebDAV 的账号配置本身上传到云端。

### 坚果云配置 {#坚果云配置}

坚果云免费账户可以用于这个场景。第三方应用应使用单独生成的应用密码，而不是坚果云登录密码：

```text
URL：https://dav.jianguoyun.com/dav/
用户名：坚果云注册邮箱
密码：坚果云“第三方应用管理”中生成的应用密码
```

生成路径大致为：

```text
坚果云 → 账户信息 → 安全选项 → 第三方应用管理 → 添加应用密码
```

免费版 WebDAV 有请求频率和月度上传/下载流量限制。官方帮助页目前说明免费用户每 30 分钟最多 600 次 WebDAV 请求；具体套餐流量以后可能调整，以坚果云官网为准。Kazumi 的记录文件很小，正常个人同步通常不会成为流量压力。

### 首次从 Mac 同步到 iPad {#首次从-mac-同步到-ipad}

为了避免空白设备覆盖已有记录，我采用单向确定主数据后再开始双向使用：

1. 先在有完整记录的 Mac 版 Kazumi 配置 WebDAV 并测试连接。
2. 在 Mac 上先执行上传或同步，确认云端已经生成 Kazumi 的同步数据。
3. 再在空白 iPad 上填写同一组 URL、邮箱和应用密码。
4. iPad 首次执行下载或同步，确认观看记录和追番数据出现。
5. 两端数据一致后，才开始日常双向同步。

设备切换前，最好先在刚使用完的设备上手动同步；到另一端后再同步一次。不要在首次连接时让空白 iPad 抢先上传。

### 续签、更新和重装对 WebDAV 的影响 {#续签更新和重装对-webdav-的影响}

| 操作 | WebDAV 配置 | 云端观看记录 |
| --- | --- | --- |
| SideStore `Refresh All` | 保留 | 保留 |
| 在原位置覆盖更新 LiveContainer/Kazumi | 通常保留，更新前仍建议确认同步成功 | 保留 |
| 删除 Kazumi 的访客数据容器 | 需要重新填写 | 已成功上传的记录仍在 |
| 删除整个 LiveContainer | 宿主内访客数据和本地配置可能一起被删除 | 已成功上传的记录仍在 |

Kazumi 源码显示 WebDAV URL、用户名和密码从本地设置存储读取。因此，续签不会要求每周重新导入 WebDAV；彻底删除应用数据后则需要重新填写，再从云端下载或同步。

## 六、值得尝试的 IPA {#六值得尝试的-ipa}

优先从项目官网、官方 GitHub Releases 或官方 SideStore/AltStore Source 获取应用。下面的“LiveContainer 情况”是功能特征判断

| 应用                                                       | 用途与官方来源             | JIT    | LiveContainer 情况与风险                            |
| -------------------------------------------------------- | ------------------- | ------ | ---------------------------------------------- |
| [Kazumi](https://github.com/Predidit/Kazumi)             | 动画聚合播放器；本次已实际跑通     | 不需要    | 适合；内容源与版权责任仍由使用者自行判断                           |
| [Aidoku](https://github.com/Aidoku/Aidoku)               | 开源、无广告的漫画阅读器        | 不需要    | 通常适合；扩展源是额外信任边界                                |
| [Mangayomi](https://github.com/kodjodevf/mangayomi)      | 漫画、小说、动画的跨平台阅读/播放工具 | 通常不需要  | 官方明确警告第三方下载站不可信，只使用官方仓库                        |
| [Tachimanga](https://github.com/tachimanga/tachimanga)   | iOS 漫画阅读器           | 不需要    | 已有 App Store 版本时优先商店安装，没有必要为侧载而侧载              |
| [Kodi](https://kodi.tv/download/ios/)                    | 本地与家庭媒体中心           | 不需要    | 可侧载，但插件和文件访问能力可能受 LiveContainer 限制；只使用合法媒体源    |
| [iTorrent](https://github.com/XITRIX/iTorrent)           | iOS BT 客户端          | 不需要    | 后台下载可能受宿主限制；仅下载有权获取的内容                         |
| [DolphiniOS](https://github.com/OatmealDome/dolphin-ios) | GameCube/Wii 模拟器    | 强烈建议   | JIT 和系统版本兼容性变化快，应先查 SideStore/StikDebug 当前支持情况 |
| [UTM](https://github.com/utmapp/UTM)                     | 虚拟机与系统实验            | 完整性能需要 | 高阶玩法；无 JIT 的 UTM SE 可优先考虑商店版本                  |
| YouTube Plus / YTLite                                    | 修改版 YouTube 增强组件    | 不需要    | 不提供来历不明的成品 IPA；优先自行构建并使用次要账号，留意订阅、隐私和服务条款风险    |



## 七、LiveContainer 的其他玩法 {#七livecontainer-的其他玩法}

### 主屏幕快捷入口 {#主屏幕快捷入口}

可以为访客 App 生成启动快捷方式并放到主屏幕。外观更接近普通 App，但底层仍由 LiveContainer 宿主运行，宿主掉签后所有入口都会一起失效。

### 多数据容器 {#多数据容器}

同一个 App 可以建立多个数据容器，用于多账号、测试不同配置或保留干净环境。它适合实验，但不等于完整安全隔离；不要用来存放高敏感凭据。

### iPad 多任务与 PiP {#ipad-多任务与-pip}

LiveContainer 支持访客 App 的窗口化、多任务和 PiP。部分功能要求安装宿主时保留相应 App Extensions；访客 App 自己的扩展仍可能无法注册。

### StikDebug 与 JIT {#stikdebug-与-jit}

模拟器、虚拟机或部分游戏需要 JIT。可以按当前 SideStore 文档使用 StikDebug，但 JIT 支持高度依赖 iOS 版本，不能把旧教程视为永久有效。Kazumi、Aidoku 这类普通 App 不应为了“看起来高级”而额外开启 JIT。

### SideStore Sources {#sidestore-sources}

Source 可以集中展示安装和更新入口，减少手工寻找 IPA 的成本。建议只添加项目官方 Source；添加前检查最终下载 URL 是否仍指向官方仓库。Source 能自动更新元数据，不代表它能自动替应用续签。

## 八、安全边界 {#八安全边界}

- 只使用 LiveContainer、SideStore、iLoader 和访客 App 的官方发布渠道。
- 不把主 Apple Account、银行账号、密码库或工作机密交给未知 IPA。
- Shadowrocket 登录阶段只做流量转发，不对 Apple 域名启用 HTTPS 解密。
- 不在笔记、截图、Issue 或日志中暴露 Apple Account、应用密码、pairing file、UDID、代理订阅和节点信息。
- `Refresh All` 是维护签名的低风险例行操作；删除 LiveContainer 会影响其内部所有访客 App 和本地配置，操作前先做 WebDAV 同步或其他备份。
- 使用 Kazumi、阅读器、Kodi、下载器和模拟器时，应遵守所在地法律、内容授权和对应服务条款。

## 参考资料 {#参考资料}

资料核对日期：2026-08-28。

- [Kazumi：iOS 自签教程](https://kazumi.app/docs/misc/how-to-install-in-ios/)
- [Kazumi：功能模块与 WebDAV 同步](https://kazumi.app/docs/intro/module-details/)
- [Kazumi：WebDAV 配置源码](https://github.com/Predidit/Kazumi/blob/main/lib/pages/webdav_editor/webdav_editor_page.dart)
- [Kazumi \#1827：Invalid file / Guru Meditation](https://github.com/Predidit/Kazumi/issues/1827)
- [SideStore：安装说明](https://docs.sidestore.io/docs/installation/install)
- [SideStore：安装前提与 LocalDevVPN](https://docs.sidestore.io/docs/installation/prerequisites)
- [SideStore：错误代码](https://docs.sidestore.io/docs/troubleshooting/error-codes)
- [SideStore：App Sources](https://docs.sidestore.io/docs/advanced/app-sources)
- [SideStore \#1143：NSCocoaErrorDomain 3840](https://github.com/SideStore/SideStore/issues/1143#issuecomment-3785285152)
- [LiveContainer 官方仓库](https://github.com/LiveContainer/LiveContainer)
- [LiveContainer + SideStore 安装指南](https://github.com/LiveContainer/livecontainer.github.io/blob/main/docs/installation/lc_sidestore.md)
- [Sidestore-ClashMi：`loopback-address` 的背景参考](https://github.com/tom-snow/Sidestore-ClashMi)
- [坚果云客户端下载](https://www.jianguoyun.com/s/downloads)
- [坚果云：第三方应用授权与 WebDAV 应用密码](https://help.jianguoyun.com/?p=2064)
- [uYouPlus \#1627：旧版 IPA 侧载错误案例](https://github.com/qnblackcat/uYouPlus/issues/1627)
- [YouTube Plus / YTLite 官方仓库](https://github.com/dayanch96/YTLite)
