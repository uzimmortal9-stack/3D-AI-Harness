"""Forge3D AI chat — test the platform with your own model.

Slash commands:
  /provider openai|anthropic|openrouter|ollama|custom
  /model <name>            e.g. gpt-4o, claude-sonnet-4-5, llama3.1
  /key <api-key>           stored to config/forge3d.config.json (local only)
  /base <url>              custom OpenAI-compatible endpoint
  /run                     compile the last script produced by the AI
  /render                  software-render current scene
  /doctor                  health-check current scene
  /help  /exit
"""
import os
import shlex

from . import llm
from .orchestrator import AGENT_SYSTEM, _extract_script

CHAT_HELP = __doc__


class ChatState:
    def __init__(self, provider=None, model=None):
        self.provider = provider
        self.model = model
        self.api_key = None
        self.base_url = None
        self.messages = []
        self.scene_file = "chat_scene.forge"
        self.scene = None


def _try_compile(state):
    from forge3d.forge_lang import Interpreter, ForgeSyntaxError, ForgeLangError
    from forge3d.doctor import examine_scene, report_text
    try:
        interp = Interpreter(".")
        scene, rep = interp.run_file(state.scene_file)
        state.scene = scene
        print(f"[forge3d] compiled OK — {scene.stats()['meshes']} meshes, "
              f"{scene.stats()['triangles']} tris")
        report = examine_scene(scene)
        print(report_text(report))
        return report
    except (ForgeSyntaxError, ForgeLangError) as e:
        print(f"[forge3d] COMPILE ERROR: {e}")
        return None


def _render(state):
    if state.scene is None:
        print("[forge3d] nothing compiled yet — /run first")
        return
    from forge3d.raster import render_scene
    from forge3d.pngio import write_png
    write_png("chat_render.png", render_scene(state.scene, 640, 480))
    print("[forge3d] rendered -> chat_render.png  (open it, or `observe`)")


def chat_loop(provider=None, model=None):
    state = ChatState(provider, model)
    print("Forge3D chat — bring your own model. /help for commands.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.startswith("/"):
            parts = shlex.split(line[1:])
            if not parts:
                continue
            cmd, args = parts[0], parts[1:]
            if cmd == "exit":
                return
            elif cmd == "help":
                print(CHAT_HELP)
            elif cmd == "provider":
                state.provider = args[0] if args else None
                print(f"[forge3d] provider = {state.provider}")
            elif cmd == "model":
                state.model = " ".join(args) or None
                print(f"[forge3d] model = {state.model}")
            elif cmd == "base":
                state.base_url = args[0] if args else None
                print(f"[forge3d] base_url = {state.base_url}")
            elif cmd == "key":
                state.api_key = args[0] if args else None
                cfg = llm.load_config()
                cfg.update({"provider": state.provider, "model": state.model,
                            "api_key": state.api_key})
                llm.save_config(cfg)
                print("[forge3d] key stored locally in "
                      "config/forge3d.config.json")
            elif cmd == "run":
                _try_compile(state)
            elif cmd == "render":
                _render(state)
            elif cmd == "doctor":
                if state.scene is not None:
                    from forge3d.doctor import examine_scene, report_text
                    print(report_text(examine_scene(state.scene)))
            else:
                print("unknown command — /help")
            continue
        state.messages.append({"role": "user", "content": line})
        try:
            reply = llm.chat(state.messages, system=AGENT_SYSTEM,
                             provider=state.provider, model=state.model,
                             api_key=state.api_key, base_url=state.base_url)
        except llm.LLMError as e:
            print(f"[forge3d] LLM ERROR: {e}")
            continue
        state.messages.append({"role": "assistant", "content": reply})
        print("ai>", reply[:1200])
        script = _extract_script(reply)
        if "primitive" in script:
            with open(state.scene_file, "w") as f:
                f.write(script)
            print(f"[forge3d] saved -> {state.scene_file}; auto-compiling…")
            if _try_compile(state) is not None:
                _render(state)
