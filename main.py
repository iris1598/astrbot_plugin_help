import collections
from typing import Dict, List, Optional


from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Image
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.filter.permission import PermissionType, PermissionTypeFilter
from astrbot.core.star.star_handler import star_handlers_registry, StarHandlerMetadata

from .draw import AstrBotHelpDrawer


@register(
    "astrbot_plugin_help", "tinker", "查看所有命令，包括插件，返回一张帮助图片", "1.1.3"
)
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.drawer = AstrBotHelpDrawer(config)


    @filter.command("helps", alias={"帮助", "菜单", "功能", "幫助", "菜單"})
    async def get_help(self, event: AstrMessageEvent):
        """获取插件命令列表并生成命令帮助图片"""
        help_msg = self.get_all_commands()
        if not help_msg:
            yield event.plain_result("没有找到任何插件或命令")
            return
        image = self.drawer.draw_help_image(help_msg)
        yield event.chain_result([Image.fromBytes(image)])


    def _get_permission_level(self, handler: StarHandlerMetadata) -> str:
        """提取指令权限等级: admin/member/everyone"""
        for filter_ in handler.event_filters:
            if isinstance(filter_, PermissionTypeFilter):
                return (
                    "admin"
                    if filter_.permission_type == PermissionType.ADMIN
                    else "member"
                )
        return "everyone"


    def _should_include_command(self, permission_level: str) -> bool:
        """根据配置决定是否显示该权限级别的命令"""
        if getattr(self.config, "show_all_cmds", False):
            return True
        return permission_level != "admin"


    def _get_plugin_display_name_map(self) -> Dict[str, str]:
        """解析配置中的插件显示名称映射"""
        mapping: Dict[str, str] = {}
        configured_names = getattr(self.config, "plugin_display_names", []) or []
        if not isinstance(configured_names, list):
            return mapping

        for item in configured_names:
            if not isinstance(item, str):
                continue
            raw = item.strip()
            if not raw or ":" not in raw:
                continue
            plugin_name, display_name = raw.split(":", 1)
            plugin_name = plugin_name.strip()
            display_name = display_name.strip()
            if plugin_name and display_name:
                mapping[plugin_name] = display_name
        return mapping


    def get_all_commands(self) -> Dict[str, List[dict]]:
        """获取所有其他插件及其命令列表, 格式为 {plugin_name: [{command, desc, permission}]}"""
        # 使用 defaultdict 可以方便地向列表中添加元素
        plugin_commands: Dict[str, List[dict]] = collections.defaultdict(list)
        plugin_command_keys: Dict[str, set[tuple[str, str, str]]] = collections.defaultdict(set)
        try:
            # 获取所有插件的元数据，并且去掉未激活的
            all_stars_metadata = self.context.get_all_stars()
            all_stars_metadata = [star for star in all_stars_metadata if star.activated]
            logger.debug(f"找到 {len(all_stars_metadata)} 个激活的插件")
            

        except Exception as e:
            logger.error(f"获取插件列表失败: {e}")
            return {}  # 出错时返回空字典
        
        if not all_stars_metadata:
            logger.warning("没有找到任何插件")
            return {}  # 没有插件时返回空字典

        display_name_map = self._get_plugin_display_name_map()
        

        for star in all_stars_metadata:
            plugin_name = getattr(star, "name", "未知插件") # 插件内部名
            plugin_native_displayname = (getattr(star, "display_name", "") or "").strip()
            plugin_displayname = (
                plugin_native_displayname
                or display_name_map.get(plugin_name, "")
                or plugin_name
            )  # 用于展示的名称，优先插件内定义，再回退配置映射，最后回退内部名
            plugin_instance = getattr(star, "star_cls", None) # 插件的类对象
            module_path = getattr(star, "module_path", None)  # 插件的模块路径
            
            if (
                plugin_name == "astrbot"
                or plugin_name == "astrbot_plugin_help"
                or plugin_name == "astrbot-reminder"
            ):
                # 跳过自身和核心插件
                continue

            # 内置命令插件的显示由配置控制，默认显示，如果配置里 show_builtin_cmds 是 False 则跳过
            if (
                plugin_name == "builtin_commands" 
                and not getattr(self.config, "show_builtin_cmds", True)
            ):
                continue

            # 进行必要的检查
            if (
                not plugin_name
                or not module_path
                or not isinstance(plugin_instance, Star)
            ):
                # 如果实例无效或名称/路径缺失，记录警告并跳过
                # 注意：这里检查了 module_path 是否存在，因为后面需要用它来匹配 handler
                logger.warning(
                    f"插件 '{plugin_name}' (模块: {module_path}) 的元数据无效或不完整，已跳过。"
                )
                continue

            # 遍历所有注册的处理器
            for handler in star_handlers_registry:
                # 确保处理器元数据有效且类型正确 (虽然原始代码有 assert，这里加个检查更安全)
                if not isinstance(handler, StarHandlerMetadata):
                    continue
                # 检查此处理器是否属于当前遍历的插件 (通过模块路径匹配)
                if handler.handler_module_path != module_path:
                    continue
                command_name: Optional[str] = None
                description: Optional[str] = handler.desc  # 获取描述信息
                # 遍历处理器的过滤器，查找命令或命令组
                for filter_ in handler.event_filters:
                    if isinstance(filter_, CommandFilter):
                        command_name = filter_.command_name
                        break  # 找到一个命令即可，跳出过滤器循环
                    elif isinstance(filter_, CommandGroupFilter):
                        command_name = filter_.group_name
                        break  # 找到一个命令组即可
                # 如果找到了命令或命令组名称
                if command_name:
                    permission_level = self._get_permission_level(handler)
                    if not self._should_include_command(permission_level):
                        continue

                    desc_text = (description or "").strip()
                    dedupe_key = (command_name, desc_text, permission_level)
                    if dedupe_key in plugin_command_keys[plugin_displayname]:
                        continue

                    plugin_command_keys[plugin_displayname].add(dedupe_key)
                    plugin_commands[plugin_displayname].append(
                        {
                            "command": command_name,
                            "desc": desc_text,
                            "permission": permission_level,
                        }
                    )
        return dict(plugin_commands)
