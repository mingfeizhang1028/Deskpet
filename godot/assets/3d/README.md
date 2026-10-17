# 芽砚 3D 资源

把 Blender 导出的正式角色放在这里，文件名固定为 `yayan_v001.glb`。当前运行时会在资源存在且能加载为 `PackedScene` 时显示 3D 视图；资源缺失或损坏时自动继续使用 PNG 回退，不影响窗口、bridge 或聊天。

## 导出约定

- glTF 2.0 Binary（`.glb`）
- 应用位置、旋转和缩放变换，单位使用米
- 根节点保持在角色脚底中心，面朝 Godot 摄像机的 -Z 方向
- 材质、骨骼、权重和动画一起导出
- 动画名称使用小写英文：`idle`、`blink`、`breathe`、`walk`、`turn_left`、`turn_right`、`stop`、`happy`、`concerned`、`curious`、`sleepy`
- 新的网格或权重结构使用递增版本名（例如 `yayan_v002.glb`），并同步修改 `pet_3d_view.gd` 的 `MODEL_PATH`

第一版骨骼最小集合：`root/body/chest/head`，耳朵 `ear_l`、`ear_r`，尾巴 `tail_01` 至 `tail_04`，四条腿和可选的 `jaw`。眼皮可用 blend shape 或缩放实现。

