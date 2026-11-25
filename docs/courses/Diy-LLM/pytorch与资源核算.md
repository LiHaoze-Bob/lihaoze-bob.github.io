---
tags:
- pytorch
- resource-accounting
- memory-bound
- roofline
- mixed-precision
title: pytorch与资源核算
---
## 资源核算 {#资源核算}
用napkin math快速估算LLM的训练
分成时间和空间两个维度，就是[Growth](../Agents-CMU/lec03.md#growth)中所说的efficiency和capacity

### 时间估算 {#时间估算}
对于时间，可以关注两点，计算时间和通信时间

FLOPs(Floating Point Operations)是浮点运算次数，而训练模型的本质就是进行FLOPs，有一个经验公式，至于为什么这样是准确的，本文后面会计算


$$
总 计 算 量 \approx 6 \times 参数量 \times \text{Token}数量
$$



然后可以查询训练GPU的峰值算力，值得注意的是，NVIDIA如果采用2：4结构化稀疏，那么算力要减半，因为通常我们训练使用稠密的模型。结构化稀疏指的是将参数的固定部分设定为0，达到快速运算的效果，但是这样会降低模型的能力。

有这么快的计算速度，还需要足够快的内存带宽。算数强度是每搬运一个byte进来，需要做多少flop，和算法有关。加速器强度是每实际搬运一个byte，可以做多少flop，和硬件本身有关
- 算术强度 < 加速器强度 → **Memory-bound**
- 算术强度 > 加速器强度 → **Compute-bound**
![](https://datawhalechina.github.io/diy-llm/assets/3-13-Roofline%E5%88%86%E6%9E%90.CaIPrhKU.png)
上图是roofline，会发现，对于algo1，转折点左侧随着硬件的升级而优化，是memory bound，右侧就是compute bound，硬件的flops再怎么提升，也不可能提高，对于同一算法。

>"对于 H100，加速器强度大约是 295。这个数字值得记一下——对于 bf16 来说，每搬运 1 字节你需要做大约 300 次浮点运算才能摆脱内存瓶颈。"

>为什么大 batch size 很重要："当你在加速器强度以下时，把矩阵变小并不会让速度变快——因为瓶颈不在计算。只有当你超过加速器强度的转折点，你才真正在**饱和使用你的 GPU**。"

对于H100，大约是3.35 TB/s

SRAM太小了，紧挨计算核心，HBM很大，模型权重在里面。
训练时，是compute bound，一次可以将所有token都乘一遍；而推理时，是memory bound，每个token进来都要把权重读一遍，却只算了一个token。
### 内存估算 {#内存估算}
一个误区是，训练显存不只有参数，还包括梯度、优化器状态、激活值等等，换句话说，任何模型训练过程中的数据，都要暂存在显卡中。所以，batchsize、序列长度，可能任何超参数都会影响内存的估算，但是既然是napkin，粗略已经够了。

模型架构与硬件之间是相互影响的。既然不同的模型架构(包括优化器、梯度等方方面面)影响着需要的显存，那么我们就需要设计出更优秀的模型架构来跨越这道门槛，这也是AI infra的一个重要的方面。反过来，思考一个问题，RNN不是挺好的吗，为什么我们需要Transformer？前者的计算是线性串行的，而后者的矩阵运算可以让GPU并行——硬件选择了RNN。

## pytorch {#pytorch}
pytorch是生态丰富的深度学习框架，它表面上作为一个python的库，实际上，它就像是一个引擎，调用CUDA\MPS等底层的C++和GPU核函数，直接在kernel上运算，而不是通过python做计算。

Tensor(张量)储存基本构建块，类似于一个多维矩阵。
张量的操作就不具体介绍了

张量的内存取决于张量的大小和一个数的表示。我们在计算机组成中学过浮点数的表示，这就存在一个内存和精度的trade-off，不同的表示方法在硬件支持程度、训练速度、训练精度有很大区别。每种方法有每种方法的有点，所以现代大模型通常使用混合精度

先不说FP32、FP16等常见的，我们来说说几个不一样的

### BF16 {#bf16}
![](https://datawhalechina.github.io/diy-llm/assets/3-7-bf16.BHwrPvEx.png)

都是16个bit，与FP16比较，它的exp更长，frac更加短，说明它更在乎范围，而不是精度

>bf16 牺牲了精度来换取范围。对于深度学习来说，范围比精度重要得多，因为数值稳定性的主要威胁是溢出/下溢，而不是尾数精度不够。


![](https://datawhalechina.github.io/diy-llm/assets/3-6-fp16.CNEGcgHE.png)

### NVFP4 {#nvfp4}


!!! idea
    模型参数的分布有什么特点，它是否是如同经过norm后一样接近正态分布，这可能对我们如何表示数字有所启发。


假定参数实际上接近正态分布，那么大部分参数在0附近，FP4正是利用此特点，4个bit可以表示
```text
-6, -4, -3, -2, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2, 3, 4, 6
```
数据被划分为一个一个block，每个blcok中的数共享一个缩放倍数

---
张量的存储机制和C语言的指针非常像，它有metadata(Tensor)，包括size、stride、dtype。数据信息放在一块连续区域，通过元数据寻址。可是，why?依旧是最好地优化硬件的性能。比如，我们需要转置时，只需要将stride颠倒过来，不需要对storage的区域操作，这就是zero-copy view，我们只是通过tensor改变我们看待数据的方式，数据本身的物理空间是不变的。

### 张量的CPU迁移 {#张量的cpu迁移}
通常，CPU的内存更大，是所有数据生命周期的起点。张量通常储存在CPU中，而我们需要将其中的张量分batch移动到GPU进行计算。在infra的世界，每一个环节都涉及着优化，迁移也是一样。

当然,如果你用的是 M1/M2/M3/M4 芯片的 Mac，苹果做了一个叫**统一内存 Unified Memory**的硬件设计——CPU 和 GPU 共用同一块物理内存，不像传统插独立显卡的台式机那样有物理搬运瓶颈

![](https://datawhalechina.github.io/diy-llm/assets/3-10-cpu%E4%B8%8Egpu%E4%B9%8B%E9%97%B4%E7%9A%84%E9%80%9A%E4%BF%A1.DRO3xZHf.png)

它们通过PCI相连，但是这是一个性能瓶颈，因为它的带宽远小于GPU内部的内存带宽。所以，我们需要尽量减少数据传输。原文在这里我感觉并没有写清楚，并不是所有的数据都是使用同样的方法。考虑一下数据的类型，可以粗浅地分为：
1.有实体文件的数据，比如训练文本、已保存的模型文件，它们原本就在硬盘中，必须要先到CPU再到GPU。
```python
y = x.to("cuda:0") # 将张量x移动到编号为0的GPU上
assert y.device == torch.device("cuda", 0) # 验证移动成功
```
但，我不能直接在GPU上创建张量，读取硬盘数据再直接复制吗🤔就像这样
```python
x = torch.empty(1000, device="cuda")   # 1. 先在 GPU 显存里占好坑位
data = read_from_disk("train.bin")     # 2. 从硬盘里读出数据
x[:] = data                            # 3. 把数据“赋值”进 GPU 坑位
```
可是，GPU并没有操作系统，它根本不认识硬盘或是文件夹，上面的代码本质上仍然是通过CPU传输。
2019年，NVIDIA实现了[GPUDirect Storage](https://developer.nvidia.com/blog/gpudirect-storage/)，CPU只负责调度，而GPU直接对接主板控制器，不用再经过CPU，瞬间加载几百个Gb的模型权重变得可能。这和前面mac的统一内存的设计其实殊途同归，但是它需要更加专用的硬件，普通消费级电脑还不能实现。它原本是用来服务科学计算、自动驾驶等领域的，结果几年后大模型横空出世，正好这项技术完美适配。
更进一步，目前的GPU在重新定义计算机的底层架构，比如将GPU和CPU焊在一起，等等

为了防止CPU拖慢，pytorch还使用了流水线异步预加载，GPU计算时，CPU采用多线程传输

2.对于没有实体文件的数据，它们是纯数学生成的，可以直接在GPU中创建，比如
```python
z = torch.zeros(32, 32, device="cuda:0") # 在GPU上直接创建一个32x32的零矩阵
```
然后验证内存分配
```python
new_memory_allocated = torch.cuda.memory_allocated() # 再次查询当前显存占用
memory_used = new_memory_allocated - memory_allocated # 计算新增的显存占用
assert memory_used == 2 * (32 * 32 * 4) # 验证：新增了2个32x32的矩阵，每个元素是4字节的float
```

## 计算效率 {#计算效率}
回收第一部分，下面我们结合模型的架构看一看实际的的计算效率

首先，这里提供一些已披露的数据，帮助我们建立一些直观的认识
- GPT-3 (2020年)：训练耗时约$3.14*10^{23}$FLOPs
- NVIDIA H100峰值性能为1979 TFLOP/s，在密集矩阵乘法的情况下，性能为其一半

### 前向传播 {#前向传播}
可以证明，线性模型前向传播中，$FLOPs \approx 2 \times token数量 \times 模型参数量$。通过矩阵乘法和加法的统计就可以证明，这里不赘述。
现代深度模型，比如transformer，虽然有其他很多操作，但是矩阵乘法依然是大多数，所以，粗略估算时，只需要计算所有的矩阵乘法。

benchmark为MFU，是实测flops除以理论峰值flops，MFU大于0.5被认为是相当不错的性能

MFU = min(1, 算术强度 / 加速器强度)

由于我是intel mac，没有cuda，可以通过以下命令查看cpu的峰值
```bash
sysctl -n machdep.cpu.brand_string
sysctl -n hw.physicalcpu hw.logicalcpu
```
通过计算可以得出我的cpu理论的计算峰值为499.2GFLOPs
贴一下我的实验结果 my_cpu_mfu
```text
当前 PyTorch CPU 线程数: 6
[纯矩阵乘法] 单次耗时: 40.70 ms | 实际算力: 422.13 GFLOPS
[模拟训练] 参数量: 4.19M | 单步耗时: 55.46 ms | 有效模型算力: 232.33 GFLOPS
假设理论峰值为 499.2 GFLOPS 时，训练 MFU ≈ 46.54%
```
- 训练模型，虽然大部分都是矩阵乘法，但是多了很多操作，相比纯矩阵乘法，性能下降很多
- 对比H100，它的算力是我的cpu的几千倍

### 反向传播 {#反向传播}
反向传播的计算量大致为4ND，除了第一层没有梯度，所以回到开头，总训练量大致是6ND

具体的数学推导可以看原文，~~具体写好像也没什么必要，it's math~~，大致就是，权重的梯度和输入激活值的梯度计算都是2ND，所以一共是4ND

## 模型构建 {#模型构建}
做一个toy model

为了解决梯度爆炸和消失的问题，需要对参数进行初始化。方法依旧有很多种

截断正态分布
```python
std = 1.0 / math.sqrt(input_dim)
w = nn.Parameter(
    nn.init.trunc_normal_(
        torch.empty(input_dim, output_dim),
        mean=0.0,
        std=std,
        a=-2.0 * std,  # 严格截断在 2 倍标准差内
        b=2.0 * std,
    )
)
```

刚开始我推理的输出是
```text
测试输入 [1, 2, 3] | 真实答案: 5.0000 | 模型预测: 2.3634
```
这时候误差特别大
> @gemini
> 先别怀疑自己，**你的代码没有任何问题，模型其实大概率已经学得很好了——之所以 [1, 2, 3] 猜成 2.3634，是因为我刚才给你出了一道“超纲题”！**
> 
> 你先看一眼终端里 **Epoch 200** 打印出来的 Train Loss 和 Val Loss 是多少？我猜它们大概率已经降到 **0.01 ~ 0.05** 左右（非常小了）！
> 
> 那为什么考卷分数这么高，一测 [1, 2, 3] 却猜出 2.3634，差了将近一半呢？这正好撞上了深度学习里最著名的一个现象——**分布外泛化失败（Out-of-Distribution / 外推失败）**！

被gemini戏耍了🤣
原来，代码中的训练数据是标准正态分布，并不能很好地拟合数据范围外的输入。GELU在范围外变成一条直线
```python
X = torch.randn(500, 3, device=device)
```
实际上，如果改成适当的数据并扩大数据范围，就可以得到接近的拟合
```python
X = torch.rand(2000, 3, device=device) * 8 - 4   # 让所有特征均匀覆盖 [-4, +4]
# 再把切分改成 [:1600] 和 [1600:]，epochs 改成 500
```
可见，数据的质量和数量对于模型训练的重要性

此外还有，数据加载，可以通过一个加载器
```python
def get_batch(data: np.array, batch_size: int, sequence_length: int, device: str) -> torch.Tensor:
    # 随机采样起始位置
    start_indices = torch.randint(len(data) - sequence_length, (batch_size,)) 
    assert start_indices.size() == torch.Size([batch_size]) # 断言验证了生成的索引数量正确

    # 根据起始索引提取数据
    x = torch.tensor([data[start:start + sequence_length] for start in start_indices]) 
    assert x.size() == torch.Size([batch_size, sequence_length])

    # 固定内存（Pinned Memory）优化
    if torch.cuda.is_available():
        x = x.pin_memory()

    # 异步数据传输
    x = x.to(device, non_blocking=True)
```

具体的优化器、checkpoint等细节就不赘述了，在[LLMs 101](../CS312-Stanford/LLMs%20101.md)或是其他笔记中都有详细叙述
