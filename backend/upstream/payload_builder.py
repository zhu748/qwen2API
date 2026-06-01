import time
import uuid


CUSTOM_TOOL_COMPAT_FEATURE_CONFIG = {
    "thinking_enabled": True,
    "output_schema": "phase",
    "research_mode": "normal",
    "auto_thinking": True,
    "thinking_mode": "Auto",
    "thinking_format": "summary",
    "auto_search": False,
    "code_interpreter": False,
    "plugins_enabled": False,
}

CUSTOM_TOOL_LOW_LATENCY_OVERRIDES = {
    "thinking_enabled": False,
    "auto_thinking": False,
    "thinking_mode": "Disabled",
}

IMAGE_CHAT_TYPES = {"image_gen", "t2i"}
VIDEO_CHAT_TYPES = {"t2v"}


def _apply_thinking_config(feature_config: dict, enabled: bool) -> None:
    feature_config.update(
        {
            "thinking_enabled": enabled,
            "auto_thinking": enabled,
            "thinking_mode": "Auto" if enabled else "Disabled",
        }
    )


def build_chat_payload(
    chat_id: str,
    model: str,
    content: str,
    has_custom_tools: bool = False,
    files: list[dict] | None = None,
    chat_type: str = "t2t",
    image_options: dict | None = None,
    thinking_enabled: bool | None = None,
    enable_search: bool = False,
) -> dict:
    ts = int(time.time())
    is_image_gen = chat_type in IMAGE_CHAT_TYPES
    is_video_gen = chat_type in VIDEO_CHAT_TYPES
    image_options = image_options or {}
    feature_config = {
        **CUSTOM_TOOL_COMPAT_FEATURE_CONFIG,
        **(CUSTOM_TOOL_LOW_LATENCY_OVERRIDES if has_custom_tools else {}),
        # Our Anthropic/OpenAI bridge relies on textual JSON/XML tool directives
        # that are parsed locally. Enabling Qwen native function_calling here causes
        # upstream interception such as `Tool Read/Bash does not exists.` for custom
        # local tools that only exist in the bridge layer.
        "function_calling": False,
        # Additional safeguards to prevent tool call interception
        "enable_tools": False,
        "enable_function_call": False,
        "tool_choice": "none",
        "auto_search": bool(enable_search or chat_type == "deep_research"),
        "plugins_enabled": is_image_gen,
        "image_gen": is_image_gen,
        "image_generation": is_image_gen,
    }
    if thinking_enabled is not None:
        _apply_thinking_config(feature_config, bool(thinking_enabled))
    if is_image_gen or is_video_gen:
        _apply_thinking_config(feature_config, False)
    if is_image_gen:
        feature_config.update(
            {
                "image_size": image_options.get("size"),
                "image_ratio": image_options.get("ratio"),
                "aspect_ratio": image_options.get("ratio"),
                "width": image_options.get("width"),
                "height": image_options.get("height"),
            }
        )
        feature_config = {k: v for k, v in feature_config.items() if v is not None}

    message_extra_meta = {"subChatType": chat_type}
    if is_image_gen:
        message_extra_meta.update(
            {
                "imageSize": image_options.get("size"),
                "imageRatio": image_options.get("ratio"),
                "aspectRatio": image_options.get("ratio"),
                "width": image_options.get("width"),
                "height": image_options.get("height"),
            }
        )
        message_extra_meta = {k: v for k, v in message_extra_meta.items() if v is not None}

    return {
        "stream": True,
        "version": "2.1",
        "incremental_output": True,
        "chat_id": chat_id,
        "chat_mode": "normal",
        "model": model,
        "parent_id": None,
        "messages": [
            {
                "fid": str(uuid.uuid4()),
                "parentId": None,
                "childrenIds": [str(uuid.uuid4())],
                "role": "user",
                "content": content,
                "user_action": "chat",
                "files": files or [],
                "timestamp": ts,
                "models": [model],
                "chat_type": chat_type,
                "feature_config": feature_config,
                "extra": {"meta": message_extra_meta},
                "sub_chat_type": chat_type,
                "parent_id": None,
            }
        ],
        "timestamp": ts,
        **({"image_options": image_options} if is_image_gen and image_options else {}),
    }
