import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.handlers import reminder_messages as msg

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "line_rich_menu" / "setup_rich_menu.py"


@pytest.fixture(scope="module")
def setup_module_():
    spec = importlib.util.spec_from_file_location("setup_rich_menu", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_menu_postbacks_match_handler(setup_module_):
    menu = setup_module_.build_rich_menu()
    data = [a["action"]["data"] for a in menu["areas"]]
    # サーバー側のハンドラーと postback の値がずれていないこと
    assert data == [msg.ACTION_MENU_REMINDER, msg.ACTION_MENU_LIST]
    assert all("displayText" not in a["action"] for a in menu["areas"])


def test_menu_areas_cover_whole_image(setup_module_):
    menu = setup_module_.build_rich_menu()
    left, right = (a["bounds"] for a in menu["areas"])
    assert left["x"] == 0 and left["width"] + right["width"] == menu["size"]["width"]
    assert right["x"] == left["width"]
    assert setup_module_.IMAGE_PATH.exists()
    assert setup_module_.IMAGE_PATH.stat().st_size < 1024 * 1024  # LINE の上限 1MB


def test_main_replaces_old_menu_and_rolls_back_on_failure(setup_module_, monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "tok")
    client = MagicMock()
    client.list_menus.return_value = [
        {"richMenuId": "old", "name": setup_module_.MENU_NAME},
        {"richMenuId": "other", "name": "別のメニュー"},
    ]
    client.create.return_value = "new"
    with patch.object(setup_module_, "LineRichMenuClient", return_value=client), \
         patch.object(setup_module_, "load_dotenv"):
        setup_module_.main()
    client.set_default.assert_called_once_with("new")
    assert [c.args[0] for c in client.delete.call_args_list] == ["old"]

    client.reset_mock()
    client.list_menus.return_value = [{"richMenuId": "old", "name": setup_module_.MENU_NAME}]
    client.create.return_value = "new2"
    client.upload_image.side_effect = RuntimeError("upload failed")
    with patch.object(setup_module_, "LineRichMenuClient", return_value=client), \
         patch.object(setup_module_, "load_dotenv"), pytest.raises(RuntimeError):
        setup_module_.main()
    # 失敗したら作りかけだけ消し、古いメニューは残す
    assert [c.args[0] for c in client.delete.call_args_list] == ["new2"]
