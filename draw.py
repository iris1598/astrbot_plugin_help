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

    # --- 画布与全局 ---
    IMG_WIDTH = 800
    PADDING = 36

    # --- 头部 ---
    HEAD_BAR_W = 56
    HEAD_BAR_H = 6
    HEAD_BAR_GAP = 16           # accent 条与标题间距
    HEADER_TEXT_GAP = 8         # 标题与副标题间距
    LOGO_TARGET_HEIGHT = 56
    LOGO_BOX_PADDING = 10
    LOGO_BOX_RADIUS = 16
    STAT_PILL_H = 36
    STAT_PILL_PAD_X = 16
    STAT_PILL_GAP = 10
    STAT_LABEL_VALUE_GAP = 6
    HEADER_TO_STAT_GAP = 20     # 标题块与统计药丸间距
    STAT_TO_CONTENT_GAP = 26    # 统计药丸与首个区块间距

    # --- 区块标题 ---
    SECTION_BAR_W = 6
    SECTION_BAR_H = 24
    SECTION_BAR_GAP = 12        # accent 竖条与区块名间距
    SECTION_ROW_H = 40          # 区块标题行高
    SECTION_DIVIDER_GAP = 8     # 标题行与分隔线间距
    SECTION_CARD_GAP = 18       # 分隔线与首行卡片间距
    SECTION_SPACING_AFTER = 36  # 区块结束后间距
    COUNT_PILL_H = 28
    COUNT_PILL_PAD_X = 14

    # --- 命令卡片（2 列大卡） ---
    CARD_MAX_COLS = 2
    CARD_SPACING = 16
    CARD_CORNER_RADIUS = 20
    CARD_PADDING_X = 18
    CARD_PADDING_TOP = 14
    CARD_PADDING_BOTTOM = 14
    NAME_DESC_SPACING = 8
    DESC_LINE_EXTRA = 6
    DESC_MAX_LINES = 4
    CARD_MIN_HEIGHT = 64

    # --- 光影 ---
    SHADOW_BLUR = 14
    SHADOW_OFFSET_Y = 6
    GLASS_BLUR = 10

    # --- 页脚 ---
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

    def _header_text_block_height(self, draw) -> int:
        title_h = self._text_height(draw, self.title_text, self.font_title)
        subtitle_h = self._text_height(draw, self.subtitle_text, self.font_subtitle)
        return self.HEAD_BAR_H + self.HEAD_BAR_GAP + title_h + self.HEADER_TEXT_GAP + subtitle_h

    def _calculate_top_area_height(self) -> int:
        measure = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        block_h = self._header_text_block_height(measure)
        if self.logo_enabled and self.resized_logo:
            logo_box_h = self.LOGO_TARGET_HEIGHT + self.LOGO_BOX_PADDING * 2
            block_h = max(block_h, logo_box_h)
        return (
            self.PADDING
            + block_h
            + self.HEADER_TO_STAT_GAP
            + self.STAT_PILL_H
            + self.STAT_TO_CONTENT_GAP
        )

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
            self.font_section = ImageFont.truetype(self.FONT_PATH_BOLD, 22)
            self.font_count = ImageFont.truetype(self.FONT_PATH_REGULAR, 12)
            self.font_stat = ImageFont.truetype(self.FONT_PATH_REGULAR, 14)
            self.font_command = ImageFont.truetype(self.FONT_PATH_BOLD, 16)
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

    # ---------------- 卡片布局（每行 2 张大卡） ----------------
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
        header_total = (
            self.SECTION_ROW_H + self.SECTION_DIVIDER_GAP + self.SECTION_CARD_GAP
        )

        for section_name, cmds in sections:
            count_text = f"{len(cmds)} 条命令"
            count_w = draw.textlength(count_text, font=self.font_count)
            layout_info.append(
                {
                    "type": "header",
                    "name": section_name,
                    "count_text": count_text,
                    "count_pill_w": int(count_w + self.COUNT_PILL_PAD_X * 2),
                    "x": self.PADDING,
                    "y": y_offset,
                    "width": self.IMG_WIDTH - self.PADDING * 2,
                    "height": header_total,
                }
            )
            y_offset += header_total

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

            y_offset += self.SECTION_SPACING_AFTER
        return layout_info

    # ---------------- 顶部区 ----------------
    def _draw_header(
        self, canvas: Image.Image, stats: List[Tuple[str, str]]
    ) -> None:
        theme = self.theme
        draw = ImageDraw.Draw(canvas)
        text_block_h = self._header_text_block_height(draw)

        # accent 短横条 + 主标题 + 副标题
        bar_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(bar_layer).rounded_rectangle(
            (
                self.PADDING,
                self.PADDING,
                self.PADDING + self.HEAD_BAR_W,
                self.PADDING + self.HEAD_BAR_H,
            ),
            radius=self.HEAD_BAR_H // 2,
            fill=(*theme.accent, 255),
        )
        canvas.alpha_composite(bar_layer)

        draw = ImageDraw.Draw(canvas)
        y_title = self.PADDING + self.HEAD_BAR_H + self.HEAD_BAR_GAP
        title_h = self._text_height(draw, self.title_text, self.font_title)
        draw.text(
            (self.PADDING, y_title),
            self.title_text,
            font=self.font_title,
            fill=theme.text_primary,
        )
        draw.text(
            (self.PADDING, y_title + title_h + self.HEADER_TEXT_GAP),
            self.subtitle_text,
            font=self.font_subtitle,
            fill=theme.text_tertiary,
        )

        # Logo 白底圆角容器，置于头部右侧、与标题块垂直居中对齐
        if self.logo_enabled and self.resized_logo:
            logo_w, logo_h = self.resized_logo.size
            pad = self.LOGO_BOX_PADDING
            box_w, box_h = logo_w + pad * 2, logo_h + pad * 2
            box_x = self.IMG_WIDTH - self.PADDING - box_w
            box_y = self.PADDING + max(0, (text_block_h - box_h) // 2)
            container = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
            ImageDraw.Draw(container).rounded_rectangle(
                (0, 0, box_w - 1, box_h - 1),
                radius=self.LOGO_BOX_RADIUS,
                fill=(255, 255, 255, 255),
                outline=(*theme.card_border, theme.logo_container_border_alpha),
                width=1,
            )
            canvas.alpha_composite(container, (box_x, box_y))
            canvas.alpha_composite(self.resized_logo, (box_x + pad, box_y + pad))

        # 统计药丸行（标签弱化色 + 数值主色）
        y_stat = self.PADDING + text_block_h + self.HEADER_TO_STAT_GAP
        x_cursor = self.PADDING
        for label, value in stats:
            label_w = draw.textlength(label, font=self.font_stat)
            value_w = draw.textlength(value, font=self.font_stat)
            pill_w = int(
                self.STAT_PILL_PAD_X
                + label_w
                + self.STAT_LABEL_VALUE_GAP
                + value_w
                + self.STAT_PILL_PAD_X
            )
            self._glass(
                canvas,
                (x_cursor, y_stat, x_cursor + pill_w, y_stat + self.STAT_PILL_H),
                radius=self.STAT_PILL_H // 2,
                tint_rgb=theme.pill_tint,
                tint_alpha=theme.pill_tint_alpha,
                border_rgb=theme.card_border,
                border_alpha=theme.pill_border_alpha,
                blur=self.GLASS_BLUR,
            )
            draw = ImageDraw.Draw(canvas)
            bbox_l = draw.textbbox((0, 0), label, font=self.font_stat)
            cy = y_stat + self.STAT_PILL_H // 2
            tx = x_cursor + self.STAT_PILL_PAD_X
            draw.text(
                (tx, cy - (bbox_l[3] + bbox_l[1]) // 2),
                label,
                font=self.font_stat,
                fill=theme.text_tertiary,
            )
            tx += label_w + self.STAT_LABEL_VALUE_GAP
            bbox_v = draw.textbbox((0, 0), value, font=self.font_stat)
            draw.text(
                (tx, cy - (bbox_v[3] + bbox_v[1]) // 2),
                value,
                font=self.font_stat,
                fill=theme.text_primary,
            )
            x_cursor += pill_w + self.STAT_PILL_GAP

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

        # 2) 毛玻璃：命令卡片 + 数量徽章
        for it in layout_info:
            if it["type"] == "card":
                self._glass(
                    canvas,
                    (it["x"], it["y"], it["x"] + it["width"], it["y"] + it["height"]),
                    radius=self.CARD_CORNER_RADIUS,
                    tint_rgb=theme.card_tint,
                    tint_alpha=theme.card_tint_alpha,
                    border_rgb=theme.card_border,
                    border_alpha=theme.card_border_alpha,
                    blur=self.GLASS_BLUR,
                )
            elif it["type"] == "header":
                pill_w = it["count_pill_w"]
                pill_x = self.IMG_WIDTH - self.PADDING - pill_w
                pill_y = it["y"] + (self.SECTION_ROW_H - self.COUNT_PILL_H) // 2
                self._glass(
                    canvas,
                    (pill_x, pill_y, pill_x + pill_w, pill_y + self.COUNT_PILL_H),
                    radius=self.COUNT_PILL_H // 2,
                    tint_rgb=theme.pill_tint,
                    tint_alpha=theme.pill_tint_alpha,
                    border_rgb=theme.card_border,
                    border_alpha=theme.pill_border_alpha,
                    blur=self.GLASS_BLUR,
                )

        # 3) 分隔线（区块标题下方 + 数量徽章共用一条基准）
        divider_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(divider_layer)
        for it in layout_info:
            if it["type"] == "header":
                line_y = it["y"] + self.SECTION_ROW_H + self.SECTION_DIVIDER_GAP
                dd.line(
                    (self.PADDING, line_y, self.IMG_WIDTH - self.PADDING, line_y),
                    fill=(*theme.divider, theme.divider_alpha),
                    width=1,
                )
        canvas.alpha_composite(divider_layer)

        # 4) 文字
        draw = ImageDraw.Draw(canvas)
        desc_line_h = self._desc_line_height(draw)
        for it in layout_info:
            if it["type"] == "header":
                cy = it["y"] + self.SECTION_ROW_H // 2
                # accent 竖条
                bar_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                ImageDraw.Draw(bar_layer).rounded_rectangle(
                    (
                        it["x"],
                        cy - self.SECTION_BAR_H // 2,
                        it["x"] + self.SECTION_BAR_W,
                        cy + self.SECTION_BAR_H // 2,
                    ),
                    radius=self.SECTION_BAR_W // 2,
                    fill=(*theme.accent, 255),
                )
                canvas.alpha_composite(bar_layer)
                draw = ImageDraw.Draw(canvas)
                # 区块名
                text_x = it["x"] + self.SECTION_BAR_W + self.SECTION_BAR_GAP
                bbox = draw.textbbox((0, 0), it["name"], font=self.font_section)
                draw.text(
                    (text_x, cy - (bbox[3] + bbox[1]) // 2),
                    it["name"],
                    font=self.font_section,
                    fill=theme.text_primary,
                )
                # 数量徽章文字
                pill_w = it["count_pill_w"]
                pill_x = self.IMG_WIDTH - self.PADDING - pill_w
                bbox = draw.textbbox((0, 0), it["count_text"], font=self.font_count)
                cw = bbox[2] - bbox[0]
                draw.text(
                    (pill_x + (pill_w - cw) // 2, cy - (bbox[3] + bbox[1]) // 2),
                    it["count_text"],
                    font=self.font_count,
                    fill=theme.text_tertiary,
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

        divider_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(divider_layer).line(
            (self.PADDING, footer_top, self.IMG_WIDTH - self.PADDING, footer_top),
            fill=(*theme.divider, theme.divider_alpha),
            width=1,
        )
        canvas.alpha_composite(divider_layer)

        draw = ImageDraw.Draw(canvas)
        cy = footer_top + self.FOOTER_HEIGHT // 2

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

        # 顶部区（accent 条 + 标题 + 统计药丸 + 右侧 Logo）
        total_cmds = sum(len(cmds) for _, cmds in sections)
        stats = [("插件", str(len(sections))), ("命令", str(total_cmds))]
        self._draw_header(canvas, stats)

        # 区块与卡片
        self._draw_sections(canvas, layout_info)

        # 页脚
        self._draw_footer(canvas, total_height)

        # 输出 PNG bytes
        with io.BytesIO() as output:
            canvas.convert("RGB").save(output, format="PNG", optimize=True)
            return output.getvalue()
