# 变更说明

## 0.运行环境
```bash
conda create -p ./env python=3.10 -y
conda activate ./env
pip install torch numpy pandas tqdm networkx scikit-learn matplotlib chinese-calendar nni rtree
conda install -c conda-forge gdal rtree 
```
## 1. 问题背景

运行以下命令时报错：

```bash
python multi_main.py --dataset Porto --diff_T 500 --pre_trained_dim 64 --rdcl 10
```

报错核心为：

```text
FileNotFoundError: /data/WeiTongLong/data/traj_gen/A_new_dataset/Porto/graph/graph_A.csv not found.
```

根因是项目代码中将数据路径硬编码为作者本地目录（`/data/WeiTongLong/...`），在当前环境不可用。

## 2. 已完成变更

### 2.1 `multi_main.py`

- 新增参数：
  - `--data_root`：可指定数据根目录。
- 路径逻辑调整：
  - 默认从 `./data/<dataset>/` 读取。
  - 若传入 `--data_root`，则从 `<data_root>/<dataset>/` 读取。
- 新增启动前必需文件检查：
  - `graph/graph_A.csv`
  - `graph/road_embed.txt`
  - `extra_file/raw_rn_dict.json`
  - `extra_file/new2raw_rid.json`
  - `extra_file/raw2new_rid.json`
  - `extra_file/rn_dict.json`
  - `gen_debug/eid_seqs.bin`（或回退 `gen_all/eid_seqs.bin`）
  - `gen_debug/rate_seqs.bin`（或回退 `gen_all/rate_seqs.bin`）
- 训练集自动回退机制：
  - 当 `gen_debug` 不存在时，自动尝试 `gen_all`。

### 2.2 `generate_data.py`

- 新增参数：
  - `--data_root`。
- 路径逻辑调整为与 `multi_main.py` 一致。
- 新增关键文件存在性检查，缺失时输出完整缺失清单和期望目录。

### 2.3 `README.md`

- 新增 “Data directory” 章节，明确数据目录结构：
  - `./data/<dataset>/graph/`
  - `./data/<dataset>/extra_file/`
  - `./data/<dataset>/road_network/`
  - `./data/<dataset>/gen_debug/`（训练调试）
- 增加 `--data_root` 使用示例。

## 3. 当前行为变化

修改前：

- 直接尝试读取作者机器绝对路径；
- 环境不一致时直接崩溃，定位困难。

修改后：

- 默认读取项目内标准路径；
- 可通过参数切换外部数据目录；
- 缺失文件时报错信息明确可操作。

## 4. 使用方式

### 4.1 默认目录（推荐）

将数据放到：

```text
./data/Porto/...
./data/Chengdu/...
```

然后运行：

```bash
python multi_main.py --dataset Porto --diff_T 500 --pre_trained_dim 64 --rdcl 10
python generate_data.py --dataset Porto --diff_T 500 --pre_trained_dim 64 --rdcl 10
```

### 4.2 自定义目录

当数据在其他位置时：

```bash
python multi_main.py --dataset Porto --data_root /path/to/data --diff_T 500 --pre_trained_dim 64 --rdcl 10
python generate_data.py --dataset Porto --data_root /path/to/data --diff_T 500 --pre_trained_dim 64 --rdcl 10
```

注意：`--data_root` 需要指向包含 `Porto/`、`Chengdu/` 子目录的上一级目录。

## 5. 验证结果

- `multi_main.py` 与 `generate_data.py` 语法检查通过（`python -m py_compile`）。
- 运行入口时，已从“作者绝对路径报错”变为“本地期望目录 + 缺失文件清单”的可操作提示。

## 6. 新增修复：GPU/CUDA 自动适配

### 6.1 问题现象

运行生成命令时报错：

```text
RuntimeError: No CUDA GPUs are available
```

但机器实际有 GPU，且 `nvidia-smi`、`torch.cuda.is_available()` 正常。

### 6.2 根因

- 脚本中存在硬编码 GPU 可见性：`CUDA_VISIBLE_DEVICES="7"`（当前机器没有 7 号卡）。
- 代码中多处硬编码 `.to("cuda:0")` / `.cuda()`，导致设备选择与实际环境不一致。

### 6.3 已完成改动

- `multi_main.py`
  - 删除硬编码 `CUDA_VISIBLE_DEVICES`。
  - `alpha` / `alpha_bar` 改为 `.to(device)`。
- `generate_data.py`
  - 删除硬编码 `CUDA_VISIBLE_DEVICES`。
  - `alpha` / `alpha_bar` 改为 `.to(device)`。
  - `torch.load(...)` 增加 `map_location=device`。
- `models/diff_util.py`
  - `std_normal` 改为接收 `device` 参数并在对应设备创建噪声张量。
  - 移除 `.cuda()`，统一改为基于输入张量设备（如 `x.device`、`Alpha.device`）。
- `models/model_utils.py`
  - `toseq()` 中 `seqs` 改为 `device=rids.device`，不再固定 `cuda:0`。

### 6.4 修复后行为

- 有 GPU 时自动使用 CUDA。
- 无 GPU 时自动回退 CPU，不再因 `cuda:0` 硬编码崩溃。
- 当前命令已可通过设备初始化阶段，后续仅在数据缺失时给出清晰文件提示。

## 7. 新增修复：`networkx` 版本兼容（`read_shp` 移除）

### 7.1 问题现象

运行时出现：

```text
AttributeError: module 'networkx' has no attribute 'read_shp'
```

### 7.2 根因

项目原逻辑依赖 `nx.read_shp`。该接口在新版本 `networkx` 中已移除。

### 7.3 已完成改动

- `common/road_network.py`
  - 重写 `load_rn_shp` 的读图逻辑，改为通过 `osgeo.ogr` 直接读取 `edges.shp`。
  - 保留原有图结构约定：节点仍为 `(lng, lat)` tuple，边上保留 `eid/coords/length` 等字段。
  - 保留空间索引 `Rtree` 与 `edge_idx` 构建逻辑。
  - 支持传入目录（自动查找 `edges.shp`）或直接传入 shapefile 路径。

### 7.4 修复后行为

- 不再依赖 `networkx` 已删除接口。
- `Porto/Chengdu` 路网可正常加载（节点/边数量可正常打印）。

## 8. 新增修复：路径拼接兼容

### 8.1 问题现象

出现路径错误：

```text
.../extra_fileraw_rn_dict.json
```

### 8.2 根因

原工具函数使用字符串拼接 `dir + file_name`，当 `dir` 不以 `/` 结尾时会拼接失败。

### 8.3 已完成改动

- `utils/utils.py`
  - 新增内部函数 `_build_path(dir_path, file_name)`。
  - `save_pkl_data/load_pkl_data/save_json_data/load_json_data` 统一改为 `os.path.join(...)`。

### 8.4 修复后行为

- 目录末尾是否带 `/` 都可正确读写文件。

## 9. 新增修复：模型加载提示优化

### 9.1 问题现象

生成阶段缺少训练权重时，直接报文件不存在，提示不够明确。

### 9.2 已完成改动

- `generate_data.py`
  - 在加载 `./results/<dataset>/val-best-model.pt` 前先检查是否存在。
  - 缺失时抛出清晰提示，并给出对应训练命令示例。

## 10. 新增修复：训练反向传播 Inplace 错误

### 10.1 问题现象

训练时报错：

```text
RuntimeError: one of the variables needed for gradient computation has been modified by an inplace operation
```

### 10.2 根因

`models/diff_module.py` 中 `Residual_block.forward` 对中间张量使用了原地加法：

- 旧逻辑：`h = x` 后 `h += part_t`

该写法会修改 autograd 依赖的张量版本，导致反传失败。

### 10.3 已完成改动

- `models/diff_module.py`
  - 改为非原地写法：`h = x + part_t`。

### 10.4 修复后行为

- 单步前向+反向传播验证通过（`loss.backward()` 正常）。
- 可继续进行 `multi_main.py` 训练流程。

## 11. 新增修复：生成阶段长度分布路径硬编码

### 11.1 问题现象

运行生成命令时报错：

```text
FileNotFoundError: ... /data/WeiTongLong/data/traj_gen/A_new_dataset/Porto/gen_all/length_distri.npy
```

### 11.2 根因

`models/multi_train.py` 的 `generate_data()` 仍使用作者机器绝对路径读取 `length_distri.npy`。

### 11.3 已完成改动

- `models/multi_train.py`
  - 移除 `length_distri.npy` 的作者绝对路径硬编码。
  - 改为优先读取：`<data_dir>/gen_all/length_distri.npy`。
  - 当该文件不存在时，自动从 `<data_dir>/gen_all/eid_seqs.bin` 统计长度分布（动态构建 `length2num`）。
  - 移除生成循环中的 `exit()`，避免中途提前退出。
- `generate_data.py`
  - 将当前解析出的数据目录写入 `args.data_dir`，供 `models/multi_train.py::generate_data()` 使用。

### 11.4 修复后行为

- 不再依赖作者本机路径。
- 在无 `length_distri.npy` 的情况下也可继续生成（回退到 `eid_seqs.bin` 统计）。
