# RT-6 VTJ 模板备份（question_import / question_preview_list）

- 备份时间：2026-10-25 08:42:38
- 分支：feat/fix-bug
- 基线提交：35a821d（RT-5 完成后）
- 用途：RT-6 将 .vtj/vue 中 v-html 渲染替换为 RichTextViewer、单题录入 textarea 替换为 RichTextEditor；本目录保存改动前的原始文件，便于回滚对照。

## 文件清单

| 原路径 | 备份文件 | 字节数 | SHA256 |
|---|---|---|---|
| .vtj\vue\question_import.vue | question_import.vue | 173558 | b682b33304d0c715711a7e48ac65de8cf1b6970d05841b6429893e1a39d4e415 |
| .vtj\vue\question_preview_list.vue | question_preview_list.vue | 66821 | d2cac6e8562af6303b12a4b2551bb6594d2f3e18d7e77c8842ff13881d695bfc |
| .vtj\files\question_import.json | question_import.json | 15236 | a51b08eb9ce88c153b2a857efad1abbfbb975adba80bfc551c97191fbf80a9b7 |
| .vtj\files\question_preview_list.json | question_preview_list.json | 1424 | bc1db6ed5f04b19b36df396fc90e9b3f17d3caccf8dd1c1a94f75d789f8d1a42 |

## 回滚方法

将上述备份文件复制回原路径即可（勿删除本备份目录）。
