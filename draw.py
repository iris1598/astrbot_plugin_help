import io
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig


# ============================ 主题系统（参考 rika_share） ============================


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class _Theme:
    """一套帮助图配色方案（token 结构与 rika_share 对齐）"""

    def __init__(
        self,
        *,
        gradient_top: str,
        gradient_bottom: str,
        text_primary: str,
        text_secondary: str,
        text_tertiary: str,
        accent: str,
        card_tint: str,
        card_tint_alpha: int,
        card_border: str,
        card_border_alpha: int,
        pill_tint: str,
        pill_tint_alpha: int,
        pill_border_alpha: int,
        divider: str,
        divider_alpha: int,
        shadow_alpha: int,
        glow_alpha: int,
        logo_container_border_alpha: int,
    ):
        self.gradient_top = _hex_to_rgb(gradient_top)
        self.gradient_bottom = _hex_to_rgb(gradient_bottom)
        self.text_primary = _hex_to_rgb(text_primary)
        self.text_secondary = _hex_to_rgb(text_secondary)
        self.text_tertiary = _hex_to_rgb(text_tertiary)
        self.accent = _hex_to_rgb(accent)
        self.card_tint = _hex_to_rgb(card_tint)
        self.card_tint_alpha = card_tint_alpha
        self.card_border = _hex_to_rgb(card_border)
        self.card_border_alpha = card_border_alpha
        self.pill_tint = _hex_to_rgb(pill_tint)
        self.pill_tint_alpha = pill_tint_alpha
        self.pill_border_alpha = pill_border_alpha
        self.divider = _hex_to_rgb(divider)
        self.divider_alpha = divider_alpha
        self.shadow_alpha = shadow_alpha
        self.glow_alpha = glow_alpha
        self.logo_container_border_alpha = logo_container_border_alpha


_THEMES = {
    # 亮色：近白渐变底 + 白玻璃卡片 + 深色描边 + 轻投影
    "light": _Theme(
        gradient_top="#FFFFFF",
        gradient_bottom="#F1F4F9",
        text_primary="#1A2130",
        text_secondary="#55607A",
        text_tertiary="#8C95A9",
        accent="#0A5AB4",
        card_tint="#FFFFFF",
        card_tint_alpha=215,
        card_border="#1B2233",
        card_border_alpha=20,
        pill_tint="#1B2233",
        pill_tint_alpha=14,
        pill_border_alpha=24,
        divider="#1B2233",
        divider_alpha=18,
        shadow_alpha=55,
        glow_alpha=22,
        logo_container_border_alpha=26,
    ),
    # 暗色：深海军蓝渐变底 + 白玻璃卡片 + 亮色描边 + 重投影
    "dark": _Theme(
        gradient_top="#242B3F",
        gradient_bottom="#12161F",
        text_primary="#F5F7FC",
        text_secondary="#AEB6C8",
        text_tertiary="#7B8598",
        accent="#7FB3FF",
        card_tint="#FFFFFF",
        card_tint_alpha=12,
        card_border="#FFFFFF",
        card_border_alpha=26,
        pill_tint="#FFFFFF",
        pill_tint_alpha=12,
        pill_border_alpha=26,
        divider="#FFFFFF",
        divider_alpha=20,
        shadow_alpha=130,
        glow_alpha=36,
        logo_container_border_alpha=40,
    ),
}


class AstrBotHelpDrawer:
    # ---------------- 常量区 ----------------
    FONT_PATH_REGULAR = os.path.join(os.path.dirname(__file__), "DouyinSansBold.otf")
    FONT_PATH_BOLD = FONT_PATH_REGULAR
    LOGO_PATH = os.path.join(os.path.dirname(__file__), "astrbot_logo.jpg")

    COLOR_LOGO_BG_REMOVE = (255, 255, 255)
    LOGO_BG_TOLERANCE = 25

    # 布局尺寸
    IMG_WIDTH = 800
    PADDING = 28
    TOP_AREA_MIN_NO_LOGO = 96
    HEADER_TEXT_GAP = 6
    LOGO_TARGET_HEIGHT = 62
    LOGO_BOX_PADDING = 10
    LOGO_BOX_RADIUS = 16
    LOGO_TEXT_GAP = 16

    SECTION_PILL_HEIGHT = 46
    SECTION_PILL_PAD_X = 20
    SECTION_MARKER_SIZE = 14
    SECTION_MARKER_GAP = 10
    SECTION_SPACING_BELOW_HEADER = 16
    SECTION_SPACING_AFTER_CARDS = 28

    CARD_MAX_COLS = 4
    CARD_SPACING = 14
    CARD_CORNER_RADIUS = 18
    CARD_PADDING_X = 14
    CARD_PADDING_TOP = 12
    CARD_PADDING_BOTTOM = 12
    NAME_DESC_SPACING = 8
    DESC_LINE_EXTRA = 6
    DESC_MAX_LINES = 6
    CARD_MIN_HEIGHT = 52

    SHADOW_BLUR = 14
    SHADOW_OFFSET_Y = 6
    GLASS_BLUR = 10

    FOOTER_HEIGHT = 56
    FOOTER_DOT_SIZE = 8
    FOOTER_DOT_GAP = 8

    # ---------------- 构造函数 ----------------
    def __init__(self, config: AstrBotConfig) -> None:
        self.config = config
        theme_name = str(getattr(config, "render_theme", "light") or "light").strip().lower()
        if theme_name not in _THEMES:
            logger.warning(f"未知主题 '{theme_name}'，回退到 light")
            theme_name = "light"
        self.theme_name = theme_name
        self.theme = _THEMES[theme_name]

        self.plugin_display_name = self._load_plugin_display_name()
        self.plugin_version = self._load_plugin_version()
        self.logo_enabled = getattr(self.config, "logo_enable", True)
        self.title_text, self.subtitle_text = self._get_header_texts()
        self._load_fonts()
        self.resized_logo = None
        if self.logo_enabled:
            self._load_logo()
        self.top_area_height = self._calculate_top_area_height()

    def _get_header_texts(self) -> Tuple[str, str]:
        title_text = (
            str(getattr(self.config, "title_help", "") or "").strip()
            or "AstrBot 命令帮助"
        )
        subtitle_text = (
            str(getattr(self.config, "title_desc", "") or "").strip()
            or "可用插件及指令列表"
        )
        return title_text, subtitle_text

    def _calculate_top_area_height(self) -> int:
        if self.logo_enabled and self.resized_logo:
            box_h = self.LOGO_TARGET_HEIGHT + self.LOGO_BOX_PADDING * 2
            return self.PADDING + box_h + self.PADDING

        measure = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        title_h = self._text_height(measure, self.title_text, self.font_title)
        subtitle_h = self._text_height(measure, self.subtitle_text, self.font_subtitle)
        computed = (
            self.PADDING + title_h + self.HEADER_TEXT_GAP + subtitle_h + self.PADDING
        )
        return max(self.TOP_AREA_MIN_NO_LOGO, computed)

    @staticmethod
    def _read_metadata_value(field_name: str) -> str:
        metadata_path = Path(__file__).resolve().with_name("metadata.yaml")
        try:
            for line in metadata_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped.startswith(f"{field_name}:"):
                    continue
                return stripped.split(":", 1)[1].split("#", 1)[0].strip().strip("\"'")
        except Exception as e:
            logger.warning(f"读取 metadata.yaml 字段 {field_name} 失败: {e}")
        return ""

    def _load_plugin_display_name(self) -> str:
        return self._read_metadata_value("display_name") or "Better_help"

    def _load_plugin_version(self) -> str:
        value = self._read_metadata_value("version")
        if value:
            if value.lower().startswith("v"):
                value = value[1:]
            return value
        return "0.0.0"

    # ---------------- 字体 & Logo ----------------
    def _load_fonts(self) -> None:
        try:
            self.font_title = ImageFont.truetype(self.FONT_PATH_BOLD, 36)
            self.font_subtitle = ImageFont.truetype(self.FONT_PATH_REGULAR, 18)
            self.font_plugin_header = ImageFont.truetype(self.FONT_PATH_BOLD, 20)
            self.font_command = ImageFont.truetype(self.FONT_PATH_BOLD, 15)
            self.font_desc = ImageFont.truetype(self.FONT_PATH_REGULAR, 13)
            self.font_footer = ImageFont.truetype(self.FONT_PATH_REGULAR, 12)
        except Exception as e:
            logger.error(f"加载字体时出错: {e}")
            exit()

    def _load_logo(self) -> None:
        try:
            logo_img = Image.open(self.LOGO_PATH).convert("RGBA")
            img_data = np.array(logo_img)
            r, g, b, a = img_data.T
            white_areas = (
                (r >= self.COLOR_LOGO_BG_REMOVE[0] - self.LOGO_BG_TOLERANCE)
                & (g >= self.COLOR_LOGO_BG_REMOVE[1] - self.LOGO_BG_TOLERANCE)
                & (b >= self.COLOR_LOGO_BG_REMOVE[2] - self.LOGO_BG_TOLERANCE)
                & (a > 128)
            )
            img_data[..., -1][white_areas.T] = 0
            logo_transparent = Image.fromarray(img_data)
            ow, oh = logo_transparent.size
            new_w = int(self.LOGO_TARGET_HEIGHT * ow / oh)
            self.resized_logo = logo_transparent.resize(
                (new_w, self.LOGO_TARGET_HEIGHT), Image.Resampling.LANCZOS
            )
        except Exception as e:
            logger.warning(f"加载或处理 Logo 时出错: {e}")
            self.resized_logo = None

    # ---------------- 文本解析 ----------------
    @staticmethod
    def _parse_single_command_list(text_list) -> List[Tuple[str, str | None]]:
        if isinstance(text_list, list) and text_list and all(
            isinstance(item, dict) for item in text_list
        ):
            commands = []
            for item in text_list:
                cmd = str(item.get("command") or "").strip()
                if not cmd:
                    continue
                desc_raw = item.get("desc")
                desc = str(desc_raw).strip() if desc_raw else None
                commands.append((cmd, desc.splitlines()[0].strip() if desc else None))
            return commands

        commands = []
        lines = (
            text_list.strip().splitlines()
            if isinstance(text_list, str)
            else [ln for ln in text_list if ln.strip()]
        )

        for line in lines:
            raw = line
            stripped = line.strip()
            if not stripped or (stripped.startswith("[") and stripped.endswith("]")):
                continue
            if (raw.startswith("  ") or raw.startswith("\t")) and commands:
                cmd, desc = commands[-1]
                commands[-1] = (cmd, (desc or "") + stripped)
                continue

            parts = None
            for sep in (" : ", " # ", "#", ":"):
                if sep in stripped:
                    parts = stripped.split(sep, 1)
                    break
            if parts and len(parts) == 2:
                cmd = (
                    parts[0][2:].strip()
                    if parts[0].startswith("- ")
                    else parts[0].strip()
                )
                desc = parts[1].strip()
            else:
                cmd = stripped[2:].strip() if stripped.startswith("- ") else stripped
                desc = None
            commands.append((cmd, desc))

        return [(c, (d.splitlines()[0].strip() if d else None)) for c, d in commands]

    def _parse_plugin_commands_sorted_grouped(
        self, plugin_dict: Dict[str, Any]
    ) -> List[Tuple[str, List[Tuple[str, str | None]]]]:

        large_plugins, small_plugins = [], []
        for name, cmds_raw in plugin_dict.items():
            if not cmds_raw:
                continue
            if name in getattr(self.config, "plugin_blacklist", []):
                continue
            cmds = self._parse_single_command_list(cmds_raw)
            if not cmds:
                continue
            (small_plugins if len(cmds) == 1 else large_plugins).append((name, cmds))

        large_plugins.sort(key=lambda x: len(x[1]), reverse=True)

        grouped_small_plugin = None
        if small_plugins:
            all_small = [c for _, cmds in small_plugins for c in cmds]
            if all_small:
                grouped_small_plugin = ("简易指令", all_small)
                logger.info(f"-> 创建 '简易指令' ({len(all_small)} 条)")

        result = []
        result.extend(large_plugins)
        if grouped_small_plugin:
            result.append(grouped_small_plugin)

        custom_list = []
        if getattr(self.config, "custom_cmds", None):
            custom_list = self._parse_single_command_list(self.config.custom_cmds)
            if custom_list:
                result.append(("自定义命令", custom_list))
                logger.info(f"-> 创建 '自定义命令' ({len(custom_list)} 条)")

        return result

    # ---------------- 绘图辅助 ----------------
    @staticmethod
    def _text_height(draw, text: str, font: ImageFont.FreeTypeFont) -> int:
        if not text:
            return 0
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]

    def _desc_line_height(self, draw) -> int:
        bbox = draw.textbbox((0, 0), "测试Ag", font=self.font_desc)
        return (bbox[3] - bbox[1]) + self.DESC_LINE_EXTRA

    @staticmethod
    def _wrap_text(
        draw, text: str, font: ImageFont.FreeTypeFont, max_width: int
    ) -> List[str]:
        """按字体实测像素宽度换行（参考 rika_share 的 _wrap），兼容 CJK。"""
        if not text:
            return []
        lines: List[str] = []
        cur = ""
        for ch in text:
            if ch == "\n":
                lines.append(cur)
                cur = ""
                continue
            candidate = cur + ch
            if not cur or draw.textlength(candidate, font=font) <= max_width:
                cur = candidate
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    @staticmethod
    def _gradient(size: Tuple[int, int], top, bottom) -> Image.Image:
        w, h = size
        grad = Image.new("RGB", (1, max(h, 1)))
        for y in range(max(h, 1)):
            ratio = y / max(h - 1, 1)
            color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
            grad.putpixel((0, y), color)
        return grad.resize((w, h))

    @staticmethod
    def _radial_glow(w: int, h: int, rgb, alpha: int) -> Image.Image:
        """一团柔和的径向光晕（品牌色渗透用）。"""
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(base).ellipse(
            (-w // 3, -h // 2, w // 2, h // 2), fill=(*rgb, alpha)
        )
        return base.filter(ImageFilter.GaussianBlur(max(w, h) // 5))

    @staticmethod
    def _glass(
        canvas: Image.Image,
        box: Tuple[int, int, int, int],
        radius: int,
        tint_rgb,
        tint_alpha: int,
        border_rgb,
        border_alpha: int,
        blur: int,
    ) -> None:
        """在画布指定区域绘制毛玻璃圆角块（真实背景模糊 + tint + 细描边）。"""
        x0, y0, x1, y1 = box
        if x1 <= x0 or y1 <= y0:
            return
        region = canvas.crop(box).filter(ImageFilter.GaussianBlur(blur))
        region.alpha_composite(Image.new("RGBA", region.size, (*tint_rgb, tint_alpha)))
        mask = Image.new("L", region.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, region.size[0] - 1, region.size[1] - 1), radius=radius, fill=255
        )
        canvas.paste(region, (x0, y0), mask)
        if border_alpha > 0:
            border_layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
            ImageDraw.Draw(border_layer).rounded_rectangle(
                (0, 0, x1 - x0 - 1, y1 - y0 - 1),
                radius=radius,
                outline=(*border_rgb, border_alpha),
                width=1,
            )
            canvas.alpha_composite(border_layer, (x0, y0))

    def _draw_card_shadows(
        self, canvas: Image.Image, boxes: List[Tuple[int, int, int, int]]
    ) -> None:
        """所有卡片阴影一次性绘制到单独层，整体模糊后混合（只模糊一次，性能好）。"""
        if not boxes or self.theme.shadow_alpha <= 0:
            return
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for x0, y0, x1, y1 in boxes:
            d.rounded_rectangle(
                (x0, y0 + self.SHADOW_OFFSET_Y, x1, y1 + self.SHADOW_OFFSET_Y),
                radius=self.CARD_CORNER_RADIUS,
                fill=(8, 12, 24, self.theme.shadow_alpha),
            )
        layer = layer.filter(ImageFilter.GaussianBlur(self.SHADOW_BLUR))
        canvas.alpha_composite(layer)

    # ---------------- 卡片布局（每行最多 4 张） ----------------
    def _layout_cards(
        self,
        sections: List[Tuple[str, List[Tuple[str, str | None]]]],
        draw,
    ) -> List[Dict]:
        layout_info: List[Dict] = []
        y_offset = self.top_area_height
        max_cols = self.CARD_MAX_COLS
        card_spacing = self.CARD_SPACING
        card_width = (
            self.IMG_WIDTH - self.PADDING * 2 - card_spacing * (max_cols - 1)
        ) // max_cols
        desc_max_width = card_width - self.CARD_PADDING_X * 2
        desc_line_h = self._desc_line_height(draw)

        for section_name, cmds in sections:
            # 区块标题胶囊宽度按文字实测
            title_w = draw.textlength(section_name, font=self.font_plugin_header)
            pill_w = int(
                self.SECTION_PILL_PAD_X
                + self.SECTION_MARKER_SIZE
                + self.SECTION_MARKER_GAP
                + title_w
                + self.SECTION_PILL_PAD_X
            )
            layout_info.append(
                {
                    "type": "header",
                    "name": section_name,
                    "x": self.PADDING,
                    "y": y_offset,
                    "width": pill_w,
                    "height": self.SECTION_PILL_HEIGHT,
                }
            )
            y_offset += self.SECTION_PILL_HEIGHT + self.SECTION_SPACING_BELOW_HEADER

            row_cards: List[Dict] = []
            col_idx = 0
            max_row_height = 0

            for cmd, desc in cmds:
                h_cmd = self._text_height(draw, cmd, self.font_command)

                wrapped_desc = self._wrap_text(
                    draw, desc or "", self.font_desc, desc_max_width
                )
                if len(wrapped_desc) > self.DESC_MAX_LINES:
                    wrapped_desc = wrapped_desc[: self.DESC_MAX_LINES]
                    last = wrapped_desc[-1]
                    while (
                        last
                        and draw.textlength(last + "…", font=self.font_desc)
                        > desc_max_width
                    ):
                        last = last[:-1]
                    wrapped_desc[-1] = last + "…"

                h_desc_total = len(wrapped_desc) * desc_line_h if wrapped_desc else 0
                card_h = max(
                    self.CARD_PADDING_TOP
                    + h_cmd
                    + (self.NAME_DESC_SPACING + h_desc_total if wrapped_desc else 0)
                    + self.CARD_PADDING_BOTTOM,
                    self.CARD_MIN_HEIGHT,
                )

                row_cards.append(
                    {
                        "type": "card",
                        "name": cmd,
                        "desc_lines": wrapped_desc,
                        "height": card_h,
                    }
                )
                max_row_height = max(max_row_height, card_h)
                col_idx += 1

                if col_idx == max_cols:
                    for i, card in enumerate(row_cards):
                        card["x"] = self.PADDING + i * (card_width + card_spacing)
                        card["y"] = y_offset
                        card["width"] = card_width
                        card["height"] = max_row_height
                    layout_info.extend(row_cards)
                    y_offset += max_row_height + card_spacing
                    row_cards = []
                    col_idx = 0
                    max_row_height = 0

            if row_cards:
                for i, card in enumerate(row_cards):
                    card["x"] = self.PADDING + i * (card_width + card_spacing)
                    card["y"] = y_offset
                    card["width"] = card_width
                    card["height"] = max_row_height
                layout_info.extend(row_cards)
                y_offset += max_row_height + card_spacing

            y_offset += self.SECTION_SPACING_AFTER_CARDS
        return layout_info

    # ---------------- 顶部区 ----------------
    def _draw_header(self, canvas: Image.Image) -> None:
        draw = ImageDraw.Draw(canvas)
        theme = self.theme

        if self.logo_enabled and self.resized_logo:
            logo_w, logo_h = self.resized_logo.size
            pad = self.LOGO_BOX_PADDING
            box = (
                self.PADDING,
                self.PADDING,
                self.PADDING + logo_w + pad * 2,
                self.PADDING + logo_h + pad * 2,
            )
            # Logo 保留白底圆角容器，深浅主题下都能保证可读性
            container = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
            ImageDraw.Draw(container).rounded_rectangle(
                (0, 0, container.size[0] - 1, container.size[1] - 1),
                radius=self.LOGO_BOX_RADIUS,
                fill=(255, 255, 255, 255),
                outline=(*theme.card_border, theme.logo_container_border_alpha),
                width=1,
            )
            canvas.alpha_composite(container, (box[0], box[1]))
            canvas.alpha_composite(self.resized_logo, (box[0] + pad, box[1] + pad))
            x_text = box[2] + self.LOGO_TEXT_GAP
            title_h = self._text_height(draw, self.title_text, self.font_title)
            subtitle_h = self._text_height(draw, self.subtitle_text, self.font_subtitle)
            block_h = title_h + self.HEADER_TEXT_GAP + subtitle_h
            y_title = self.PADDING + ((box[3] - box[1]) - block_h) // 2
        else:
            # 无 Logo 时画一条 accent 短横条作为头部装饰（rika_share 头部语言）
            bar_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(bar_layer).rounded_rectangle(
                (self.PADDING, self.PADDING, self.PADDING + 56, self.PADDING + 6),
                radius=3,
                fill=(*theme.accent, 255),
            )
            canvas.alpha_composite(bar_layer)
            x_text = self.PADDING
            y_title = self.PADDING + 16

        draw = ImageDraw.Draw(canvas)
        title_h = self._text_height(draw, self.title_text, self.font_title)
        draw.text(
            (x_text, y_title),
            self.title_text,
            font=self.font_title,
            fill=theme.text_primary,
        )
        draw.text(
            (x_text, y_title + title_h + self.HEADER_TEXT_GAP),
            self.subtitle_text,
            font=self.font_subtitle,
            fill=theme.text_tertiary,
        )

    # ---------------- 区块与卡片 ----------------
    def _draw_sections(self, canvas: Image.Image, layout_info: List[Dict]) -> None:
        theme = self.theme

        # 1) 统一绘制卡片阴影（单次模糊）
        card_boxes = [
            (it["x"], it["y"], it["x"] + it["width"], it["y"] + it["height"])
            for it in layout_info
            if it["type"] == "card"
        ]
        self._draw_card_shadows(canvas, card_boxes)

        # 2) 毛玻璃区块标题胶囊 + 毛玻璃命令卡片
        for it in layout_info:
            box = (it["x"], it["y"], it["x"] + it["width"], it["y"] + it["height"])
            if it["type"] == "header":
                self._glass(
                    canvas,
                    box,
                    radius=it["height"] // 2,
                    tint_rgb=theme.pill_tint,
                    tint_alpha=theme.pill_tint_alpha,
                    border_rgb=theme.card_border,
                    border_alpha=theme.pill_border_alpha,
                    blur=self.GLASS_BLUR,
                )
            elif it["type"] == "card":
                self._glass(
                    canvas,
                    box,
                    radius=self.CARD_CORNER_RADIUS,
                    tint_rgb=theme.card_tint,
                    tint_alpha=theme.card_tint_alpha,
                    border_rgb=theme.card_border,
                    border_alpha=theme.card_border_alpha,
                    blur=self.GLASS_BLUR,
                )

        # 3) 文字
        draw = ImageDraw.Draw(canvas)
        desc_line_h = self._desc_line_height(draw)
        for it in layout_info:
            if it["type"] == "header":
                cy = it["y"] + it["height"] // 2
                dot_x = it["x"] + self.SECTION_PILL_PAD_X
                draw.ellipse(
                    (
                        dot_x,
                        cy - self.SECTION_MARKER_SIZE // 2,
                        dot_x + self.SECTION_MARKER_SIZE,
                        cy + self.SECTION_MARKER_SIZE // 2,
                    ),
                    fill=theme.accent,
                )
                text_x = dot_x + self.SECTION_MARKER_SIZE + self.SECTION_MARKER_GAP
                bbox = draw.textbbox((0, 0), it["name"], font=self.font_plugin_header)
                draw.text(
                    (text_x, cy - (bbox[3] + bbox[1]) // 2),
                    it["name"],
                    font=self.font_plugin_header,
                    fill=theme.text_primary,
                )
            elif it["type"] == "card":
                x0, y0 = it["x"], it["y"]
                ty = y0 + self.CARD_PADDING_TOP
                draw.text(
                    (x0 + self.CARD_PADDING_X, ty),
                    it["name"],
                    font=self.font_command,
                    fill=theme.accent,
                )
                if it["desc_lines"]:
                    ty += (
                        self._text_height(draw, it["name"], self.font_command)
                        + self.NAME_DESC_SPACING
                    )
                    for line in it["desc_lines"]:
                        draw.text(
                            (x0 + self.CARD_PADDING_X, ty),
                            line,
                            font=self.font_desc,
                            fill=theme.text_secondary,
                        )
                        ty += desc_line_h

    # ---------------- 页脚 ----------------
    def _draw_footer(self, canvas: Image.Image, total_height: int) -> None:
        theme = self.theme
        footer_top = total_height - self.FOOTER_HEIGHT

        # 弱化分隔线
        divider_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(divider_layer).line(
            (self.PADDING, footer_top, self.IMG_WIDTH - self.PADDING, footer_top),
            fill=(*theme.divider, theme.divider_alpha),
            width=1,
        )
        canvas.alpha_composite(divider_layer)

        draw = ImageDraw.Draw(canvas)
        cy = footer_top + self.FOOTER_HEIGHT // 2

        # 左侧：accent 圆点 + 品牌水印
        dot_y = cy - self.FOOTER_DOT_SIZE // 2
        draw.ellipse(
            (
                self.PADDING,
                dot_y,
                self.PADDING + self.FOOTER_DOT_SIZE,
                dot_y + self.FOOTER_DOT_SIZE,
            ),
            fill=theme.accent,
        )
        brand_text = "Powered by AstrBot"
        bbox = draw.textbbox((0, 0), brand_text, font=self.font_footer)
        draw.text(
            (
                self.PADDING + self.FOOTER_DOT_SIZE + self.FOOTER_DOT_GAP,
                cy - (bbox[3] + bbox[1]) // 2,
            ),
            brand_text,
            font=self.font_footer,
            fill=theme.text_tertiary,
        )

        # 右侧：插件名 + 版本
        footer_text = f"{self.plugin_display_name} v{self.plugin_version}"
        bbox = draw.textbbox((0, 0), footer_text, font=self.font_footer)
        fw = bbox[2] - bbox[0]
        draw.text(
            (self.IMG_WIDTH - fw - self.PADDING, cy - (bbox[3] + bbox[1]) // 2),
            footer_text,
            font=self.font_footer,
            fill=theme.text_tertiary,
        )

    # ---------------- 主函数 ----------------
    def draw_help_image(self, plugin_commands_dict: Dict[str, Any]) -> bytes:
        theme = self.theme

        # 解析插件命令
        sections = self._parse_plugin_commands_sorted_grouped(plugin_commands_dict)

        # 布局测量（第一遍）
        temp_img = Image.new("RGBA", (self.IMG_WIDTH, 64), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(temp_img)
        layout_info = self._layout_cards(sections, measure_draw)
        if layout_info:
            last = layout_info[-1]
            content_bottom = last["y"] + last.get("height", 0)
        else:
            content_bottom = self.top_area_height
        total_height = int(content_bottom + self.FOOTER_HEIGHT + self.PADDING)

        # 创建最终画布（RGBA，支持阴影/毛玻璃/光晕）
        canvas = self._gradient(
            (self.IMG_WIDTH, total_height), theme.gradient_top, theme.gradient_bottom
        ).convert("RGBA")

        # 品牌色径向光晕渗透（右上 + 左下）
        glow_w, glow_h = int(self.IMG_WIDTH * 0.9), 420
        glow_tr = self._radial_glow(glow_w, glow_h, theme.accent, theme.glow_alpha)
        canvas.alpha_composite(glow_tr, (self.IMG_WIDTH - glow_w + glow_w // 3, -glow_h // 3))
        glow_bl = self._radial_glow(glow_w, glow_h, theme.accent, theme.glow_alpha)
        canvas.alpha_composite(
            glow_bl, (-glow_w // 3, total_height - glow_h + glow_h // 3)
        )

        # 顶部区（Logo + 标题）
        self._draw_header(canvas)

        # 区块与卡片
        self._draw_sections(canvas, layout_info)

        # 页脚
        self._draw_footer(canvas, total_height)

        # 输出 PNG bytes
        with io.BytesIO() as output:
            canvas.convert("RGB").save(output, format="PNG", optimize=True)
            return output.getvalue()
