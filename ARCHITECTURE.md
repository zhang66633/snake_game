# Snake Game — 项目架构与代码结构

## 文件清单

| 文件 | 用途 |
|------|------|
| `snake.py` | 主程序（约 2240 行），包含所有逻辑 |
| `settings.json` | 用户设置持久化（JSON） |
| `highscore.txt` | 最高分记录 |
| `Makefile` | C 语言版蛇的构建（与本 Python 版无关） |

---

## 一、模块总览（snake.py 自上而下）

### 1. 导入 (line 1-11)
`pygame` `random` `sys` `os` `json` `math` `array`

### 2. 常量区 (line 13-55)

| 类别 | 名称 | 值 | 说明 |
|------|------|-----|------|
| 窗口 | `WINDOW_WIDTH / HEIGHT` | 780 | 主窗口（菜单、经典模式） |
| 窗口 | `WINDOW_PVP_WIDTH / HEIGHT` | 800 | PVP 专用窗口 |
| 网格 | `GRID_CLASSIC` | 20 | 经典模式 20×20 |
| 网格 | `GRID_PVP` | 40 | PVP 模式 40×40 |
| 速度 | `SPEED_PRESETS` | 5 档 | 蜗牛(5) 慢速(8) 中速(12) 快速(16) 极速(22) FPS |
| 造型 | `SNAKE_STYLE_LABELS` | 3 种 | 经典方块 / 圆形拼接 / 分段胶囊 |
| 战斗 | `PVP_BATTLE_LIVES` | 3 | 每方初始生命数 |
| 战斗 | `BULLET_COOLDOWN` | 5 | 子弹发射冷却帧数 |
| 过渡 | `TRANSITION_FRAMES` | 10 | 页面切换淡入淡出帧数 |
| 颜色 | `BLACK` `WHITE` `GREEN` `RED` `BLUE` `BLUE_BRIGHT` `GRAY` `GRAY_DARK` `DARK_GREEN` `DARK_GREEN2` `ORANGE` `PURPLE` `DARK_BG` `GRID_COLOR` `PANEL_BG` `BORDER_COLOR` | — | 14 个颜色常量 |

### 3. 字体加载 (line 57-70)
`_get_chinese_font(size)` — 按优先级遍历系统 CJK 字体列表，找到即返回 pygame Font。

### 4. 音频系统 (line 73-177)
纯程序化合成，无外部音频文件依赖：
- `_make_tone(freq, duration_ms, volume, wave)` — 生成单个音调（支持 sine/square/saw）
- `_mk_sequence(notes)` — 将 [(freq, dur), ...] 组合为复音 Sound
- 预生成 5 个音效：`_SFX_CLICK` `_SFX_CONFIRM` `_SFX_START` `_SFX_COUNTDOWN` `_SFX_VICTORY`

---

## 二、类层次结构

```
SettingsManager      — JSON 读写，速度预设查询
SoundManager         — 封装音效/音乐播放，跟随设置开关和音量
HighScoreManager     — 最高分读写（单行文本）
Snake                — 蛇实体（移动、碰撞、渲染：3 种造型切换）
Food                 — 食物实体（随机放置、脉冲光渲染）
Bullet               — 子弹实体（移动、渲染）
ScorePopup           — 浮动 +1 文字动画
Menu                 — 所有菜单/设置/HUD 界面渲染
Game                 — 主控制器（状态机、输入、更新、渲染）
```

### 5. SettingsManager (line 211)

```
SettingsManager
├── __init__(filename)       # 加载 JSON，合并默认值
├── _path()                  # 文件路径
├── _load() / _save()        # JSON 读写（_save 仅手动调用）
├── get(key) / set(key,val)  # 读写（set 不自动保存，需批量后调 _save）
├── get_speed_fps(key)       # 将 speed_idx 转为 FPS
└── get_speed_label(key)     # 将 speed_idx 转为标签文字
```

默认设置键：
- `classic_speed_idx` / `classic_walls`
- `pvp_collision_speed_idx` / `_init_len` / `_walls` / `_food`
- `pvp_battle_speed_idx` / `_init_len` / `_food`
- `battle_length_advantage`
- `snake_style` (0/1/2)
- `sound_enabled` / `sound_volume` / `music_enabled` / `music_volume`

### 6. SoundManager (line 258)

```
SoundManager
├── __init__(settings_mgr)   # 初始化 mixer，加载音效
├── _init_mixer()            # 设置音效/音乐音量
├── _load_sounds()           # 预生成 click/confirm/start/countdown/victory
├── play(name)               # 播放指定音效（尊重 sound_enabled）
└── reload_volumes()         # 音量设置变更后调用
```

### 7. HighScoreManager (line 308)

```
HighScoreManager
├── __init__(filename)       # 加载最高分文件
├── _path() / _load() / _save()
├── add_score(score)         # 仅在超过时更新
└── get_high_score()         # 返回 int
```

### 8. Snake (line 346)

```
Snake
├── __init__(body, direction, grid_size, color, name, style=0)
├── set_direction(new_dir)   # 方向队列（MAX=3），拒绝逆向
├── move(wrap=False)         # 移动一步，wrap=True 时穿墙 (% grid_size)
├── grow()                   # 标记下次移动增长
├── check_wall_collision()   # 撞墙检测
├── check_self_collision()   # 撞自己检测
├── _seg_color(i)            # 第 i 段的渐变色（尾暗→头亮）
├── draw(screen, cell_size)  # 按 style 分发到三种绘制方法
├── _draw_style_rect(...)    # 造型 0: 等宽圆角矩形 + 转弯关节
├── _draw_style_circle(...)  # 造型 1: 重叠圆形 + 转弯关节
├── _draw_style_capsule(...) # 造型 2: 粗线胶囊身 + 圆头
├── _draw_eyes(screen, ...)  # 蛇眼（含瞳孔）
└── get_head()               # 返回蛇头坐标
```

关键属性：`body[]`（头在末尾）、`direction`、`dir_queue[]`、`grow_flag`

### 9. Food (line 470)

```
Food
├── __init__(grid_size)
├── randomize(*snake_bodies, extra_occupied)  # 避开所有占用格
└── draw(screen, cell_size)  # 圆角矩形 + sin 脉冲发光
```

### 10. Bullet (line 515)

```
Bullet
├── __init__(position, direction, grid_size, color)
├── move()                   # 每帧移动 3 格，跨格检测防穿透
└── draw(screen, cell_size)
```

### 11. ScorePopup (line 559)

```
ScorePopup
├── __init__(x, y, text, color, lifetime=20帧)
├── update()                 # lifetime--，返回是否存活
└── draw(screen, font)       # 带 alpha 衰减的浮动文字
```

### 12. Menu (line 589)

```
Menu
├── __init__(font_large, font_small, font_medium)
├── scroll 状态: help_scroll_offset, mode_scroll_offset
│
├── 装饰:
│   ├── _draw_border(screen, color, margin)    # 矩形边框 + 四角圆点
│   └── _draw_title(screen, text, y)           # 带阴影标题 + 下划线
│
├── 菜单:
│   ├── _draw_options(screen, options, ...)     # 带动画的菜单项
│   ├── draw_main(screen, selected_idx)         # 主菜单
│   ├── draw_high_score(screen, score)           # 最高分
│   └── draw_help(screen)                       # 游戏说明（支持滚轮）
│
├── 设置:
│   ├── draw_settings(screen, settings, cursor)          # 设置主页
│   ├── draw_game_settings(screen, cursor)               # 游戏设置子页
│   ├── draw_mode_settings(screen, settings, cursor, mode) # 模式设置页
│   └── _draw_volume_bar(screen, vol, y, is_sel)        # 音量条
│
└── 类变量:
    SETTINGS_ROWS / GAME_SETTINGS_ROWS / CLASSIC_SETTINGS_ROWS
    PVP_COLLISION_SETTINGS_ROWS / PVP_BATTLE_SETTINGS_ROWS / _MODE_ROWS_MAP
```

### 13. Game (line 1092) — 主控制器

```
Game
├── 状态常量:
│   MENU CLASSIC PVP_SUBMENU PVP PVP_BATTLE
│   GAME_OVER HIGH_SCORES SETTINGS GAME_SETTINGS MODE_SETTINGS HELP
│   PVP_READY PVP_PLAYING
│
├── 类变量: P1_KEYS P2_KEYS
│
├── __init__()                # 初始化 pygame、字体、管理器、状态变量
│
├── 重置:
│   ├── reset()               # 按 mode 分发
│   ├── _reset_classic()      # 经典模式：grid=20, window=780, cell=39
│   ├── _reset_pvp()          # 碰撞模式：grid=40, window=800, cell=20
│   ├── _reset_pvp_battle()   # 战斗模式：同上 + lives=3, bullets=[], cooldown=0
│   ├── _init_pvp_common()    # 两种 PVP 共享的初始化
│   └── _foods_randomize()    # 多食物不重叠随机放置
│
├── 输入 (handle_input):
│   ├── KEYDOWN 分发:
│   │   ├── _handle_menu_input(event)
│   │   ├── _handle_pvp_submenu_input(event)
│   │   ├── _handle_classic_input(event)       # ESC/P1_KEYS/R
│   │   ├── _handle_pvp_input(event)           # ESC/P1_KEYS/P2_KEYS/R/准备
│   │   ├── _handle_pvp_battle_input(event)    # 同上 + 射击键(\ F)
│   │   ├── _handle_gameover_input(event)
│   │   ├── _handle_highscores_input(event)
│   │   ├── _handle_help_input(event)
│   │   ├── _handle_settings_input(event)
│   │   ├── _handle_game_settings_input(event)
│   │   └── _handle_mode_settings_input(event)
│   └── MOUSEWHEEL: help/mode_settings 滚动偏移
│
├── 更新 (update):
│   ├── _update_classic()      # 蛇移动 + 吃食物 + 碰撞检测
│   ├── _update_pvp()          # 双蛇移动 + 吃食物 + 碰撞检测（对方蛇身）
│   └── _update_pvp_battle()   # 同上 + 子弹移动 + 命中检测 + 生命判定
│
├── 渲染:
│   ├── draw()                 # 主渲染：处理过渡动画 / _game_just_ended 捕获
│   ├── _change_screen(state)  # 触发淡入淡出过渡（自动 resize 窗口）
│   ├── _draw_state(state)     # 按状态分发渲染
│   ├── _draw_game_mode()      # 当前游戏模式画面
│   ├── _draw_classic()        # 经典模式：网格 + 蛇 + 食物 + HUD
│   ├── _draw_pvp()            # 碰撞模式：网格 + 双蛇 + 食物 + HUD + 准备覆盖
│   ├── _draw_pvp_battle()     # 战斗模式：同上 + 子弹 + 生命显示
│   ├── _draw_grid()           # 棋盘格线
│   ├── _draw_hud_bg()         # 半透明状态栏背景
│   ├── _draw_pvp_hud()        # PVP 分数 + 操作提示
│   ├── _draw_battle_hud()     # PVP 战斗 分数 + 生命条 + 操作提示
│   ├── _draw_ready_overlay()  # 准备覆盖层（battle=True 显示战斗规则）
│   ├── _draw_game_over()      # 游戏结束覆盖：得分 + 重开提示
│   └── _draw_pvp_submenu()    # PVP 子菜单
│
├── 工具:
│   ├── _shoot(snake, bullets, color)  # 发射子弹
│   ├── _toggle_fullscreen()           # F11 全屏
│   ├── _resize_window(w, h)           # 调整窗口尺寸
│   └── _get_speed_key()               # 按当前模式返回速度设置键
│
└── run()                      # 主循环：handle_input → update → draw → tick
```

---

## 三、状态流转图

```
MENU ──Enter──▶ CLASSIC ──ESC/R/死亡──▶ GAME_OVER ──Enter──▶ MENU
  │
  ├──Enter──▶ PVP_SUBMENU ──Enter──▶ PVP (碰撞) ──ESC/死亡──▶ GAME_OVER
  │                                  │
  │                                  └── PVP_BATTLE (战斗) ──ESC/死亡──▶ GAME_OVER
  │
  ├──Enter──▶ HELP ──ESC──▶ MENU
  │
  ├──Enter──▶ SETTINGS ──Enter──▶ GAME_SETTINGS ──Enter──▶ MODE_SETTINGS
  │               │                      │                     │
  │               └──ESC──▶ MENU         └──ESC──▶ SETTINGS    └──ESC──▶ GAME_SETTINGS
  │
  ├──Enter──▶ HIGH_SCORES ──ESC──▶ MENU
  │
  └──Enter──▶ 退出
```

所有状态切换通过 `_change_screen()` 触发 10 帧淡入淡出过渡。

---

## 四、数据流

```
settings.json ──load──▶ SettingsManager.data ──get──▶ Game._reset_*()
                                                      │
                                     Game.state ──────┤
                                                      │
用户输入 ──▶ handle_input() ──▶ _handle_*_input() ──▶ 修改 snake/food/bullet 状态
                                                      │
                                                      ▼
                                   update() ──▶ 碰撞检测 / 计分 / 胜负判定
                                                      │
                                                      ▼
                                   draw() ──▶ 过渡动画 / 渲染全屏
                                                      │
                                                      ▼
                                   settings._save() （仅在退出设置时）
```

---

## 五、关键设计决策

| 决策 | 说明 |
|------|------|
| 单文件 | 所有代码在 `snake.py`，无模块引入开销 |
| 程序化音效 | 不依赖外部 .wav/.mp3，`array + math.sin` 合成 |
| 方向队列 | `dir_queue` 最多 3 个，防止快速按键丢失输入 |
| PVP 独立窗口 | 800×800，游戏内 resize，退出自动恢复 780×780 |
| 蛇身渲染 | 3 种造型可选：经典方块 / 圆形拼接 / 分段胶囊，设置中切换，重启游戏生效 |
| 穿墙取模 | `move(wrap=True)` 使用 `% grid_size`，关节画线跳过跨度 >1 的段避免穿屏线 |
| 设置批量保存 | `set()` 只改内存，`_save()` 仅在退出设置界面时调用，减少磁盘 IO |
| 过渡动画 | `_change_screen()` 10 帧 alpha 混合，`_game_just_ended` 先捕获画面再过渡到 GAME_OVER |
| P1_KEYS/P2_KEYS | 类常量，消除经典/PVP/战斗三个输入处理中内联键位映射的重复 |
