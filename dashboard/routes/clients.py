from __future__ import annotations

import json
from http import HTTPStatus


def _duplicate_client_message(exc: Exception) -> str:
    message = str(exc)
    if "duplicate key value" in message and "clients_client_code_key" in message:
        return "Client code already exists."
    return message


def handle_get(handler, parts: list[str]) -> bool:
    if parts == ["api", "clients"]:
        handler.send_json(handler.repository.clients())
        return True

    if len(parts) == 4 and parts[0] == "api" and parts[1] == "clients" and parts[3] == "platforms":
        try:
            handler.send_json(handler.repository.platforms(parts[2]))
        except ValueError as exc:
            handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        return True

    if (
        len(parts) == 6
        and parts[0] == "api"
        and parts[1] == "clients"
        and parts[3] == "platforms"
        and parts[5] == "overview"
    ):
        try:
            handler.send_json(handler.repository.overview(parts[2], parts[4]))
        except ValueError as exc:
            handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        return True

    return False


def handle_post(handler, parts: list[str]) -> bool:
    if parts == ["api", "clients"]:
        length = int(handler.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(handler.rfile.read(length) or b"{}")
            handler.send_json(handler.repository.create_client(payload), HTTPStatus.CREATED)
        except (json.JSONDecodeError, ValueError) as exc:
            handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            handler.send_error_json(_duplicate_client_message(exc), HTTPStatus.BAD_REQUEST)
        return True

    if len(parts) == 3 and parts[0] == "api" and parts[1] == "clients":
        length = int(handler.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(handler.rfile.read(length) or b"{}")
            handler.send_json(handler.repository.update_client(parts[2], payload))
        except (json.JSONDecodeError, ValueError) as exc:
            handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            handler.send_error_json(_duplicate_client_message(exc), HTTPStatus.BAD_REQUEST)
        return True

    return False


def handle_put(handler, parts: list[str]) -> bool:
    if len(parts) != 3 or parts[0] != "api" or parts[1] != "clients":
        return False

    length = int(handler.headers.get("Content-Length", "0"))
    try:
        payload = json.loads(handler.rfile.read(length) or b"{}")
        handler.send_json(handler.repository.update_client(parts[2], payload))
    except (json.JSONDecodeError, ValueError) as exc:
        handler.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
    except Exception as exc:
        handler.send_error_json(_duplicate_client_message(exc), HTTPStatus.BAD_REQUEST)
    return True


def handle_delete(handler, parts: list[str]) -> bool:
    if len(parts) == 2 and parts[0] == "api" and parts[1] == "clients":
        handler.send_error_json("Client id is required", HTTPStatus.BAD_REQUEST)
        return True

    if len(parts) == 3 and parts[0] == "api" and parts[1] == "clients":
        try:
            handler.send_json(handler.repository.delete_client(parts[2]))
        except ValueError as exc:
            handler.send_error_json(str(exc), HTTPStatus.NOT_FOUND)
        except Exception as exc:
            handler.send_error_json(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
        return True

    return False
