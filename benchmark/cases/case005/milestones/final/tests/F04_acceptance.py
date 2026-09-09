# feature: F04
"""Acceptance tests for connection lifecycle, keep-alive, reuse, and pipelining.

Exercises one-cycle state walks, keep-alive iff both sides speak HTTP/1.1
and neither Connection value contains a close token, start-next-cycle,
client non-pipelining, serial server pipelining, and recoverable
start-next-cycle refusals. Event construction is FP-01. Connection
send/feed/pull is FP-02. Body framing is FP-03.
"""

from __future__ import annotations

from _harness import product_package_name, run_python
from F01_helpers import (
    connection_side_states,
    data_payload,
    event_version,
    local_protocol_error_type,
    payload_letters,
    remote_protocol_error_type,
    request_method,
    request_target,
    require_local_refusal,
    runtime_int,
    runtime_token,
    status_code,
)
from F02_helpers import (
    client_connection,
    encoded_first_line,
    event_is_kind,
    make_data,
    make_informational,
    make_request,
    make_response,
    named_state,
    need_data_token,
    peer_http_version,
    pull_next,
    require_need_data,
    require_send_bytes,
    send_event,
    server_connection,
)
from F03_helpers import (
    feed_ok,
    payload_as_bytes,
    pull_kind,
    require_our_state,
)
from F04_helpers import (
    bodied_get_pair,
    client_send_empty,
    client_sent_named_get,
    complete_empty_http11_cycle,
    connection_has_close_token,
    encoded_status_code,
    feed_public_three_gets,
    paused_result,
    pull_empty_request,
    pull_response_then_eom,
    require_both_done,
    require_both_idle,
    require_both_must_close,
    require_close_token,
    require_local_cycle_refusal,
    require_neither_error,
    require_no_close_token,
    require_paused,
    require_start_succeeded,
    require_their_state,
    runtime_final_not_204_or_200,
    runtime_final_not_408,
    runtime_host,
    runtime_informational_status,
    runtime_target,
    second_request_method,
    send_completed_eom,
    send_final_200,
    server_send_status,
    start_next_cycle,
    trailing_held_bytes,
)


# ---------------------------------------------------------------------------
# S. Library-substrate negative control
# ---------------------------------------------------------------------------


def test_reuse_cycle_round_trips_when_package_importable():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(client, host="a", target="/")
    first = pull_empty_request(server, raw)
    assert request_method(first) == b"GET"
    assert request_target(first) == b"/"
    resp = send_final_200(server)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_done(client)
    require_both_done(server)
    require_start_succeeded(start_next_cycle(client), client)
    require_start_succeeded(start_next_cycle(server), server)
    delete = client_send_empty(
        client, method="DELETE", target="/foo", host="a"
    )
    pulled = pull_empty_request(server, delete)
    print(
        f"reuse second method={request_method(pulled)!r} "
        f"target={request_target(pulled)!r}",
        flush=True,
    )
    assert request_method(pulled) == b"DELETE"
    assert request_target(pulled) == b"/foo"


def test_reuse_cycle_encode_fails_when_package_not_importable():
    pkg = product_package_name()
    code = (
        "ok = False\n"
        "try:\n"
        f"    import {pkg} as _pkg\n"
        "    _conn = _pkg.Connection(_pkg.CLIENT)\n"
        "    _ev = _pkg.Request(\n"
        "        method='GET', target='/',\n"
        "        headers=[('Host', 'a')],\n"
        "    )\n"
        "    _encoded = _conn.send(_ev)\n"
        "    if _encoded:\n"
        "        ok = True\n"
        "        print('ENCODED_REQUEST')\n"
        "except Exception as _exc:\n"
        "    print('ENCODE_UNAVAILABLE')\n"
        "    print(type(_exc).__name__)\n"
    )
    result = run_python(code=code, include_product=False)
    text = result.stdout_text
    print(f"negative-control stdout={text!r}", flush=True)
    print(f"negative-control stderr={result.stderr_text!r}", flush=True)
    assert "ENCODED_REQUEST" not in text
    assert "ENCODE_UNAVAILABLE" in text


# ---------------------------------------------------------------------------
# A. One-cycle state walk; informational stays in SEND_RESPONSE
# ---------------------------------------------------------------------------


def test_cycle_walk_idle_to_done_without_informational():
    client, server, _req = bodied_get_pair()
    resp = require_send_bytes(
        send_event(server, make_response(200, headers=[("Content-Length", "5")]))
    )
    require_our_state(server, "SEND_BODY")
    feed_ok(client, resp)
    pulled = pull_kind(client, "response")
    assert status_code(pulled) == 200
    require_their_state(client, "SEND_BODY")
    require_our_state(client, "SEND_BODY")
    body = require_send_bytes(send_event(client, make_data(b"12345")))
    require_our_state(client, "SEND_BODY")
    send_completed_eom(client)
    require_our_state(client, "DONE")
    feed_ok(server, body)
    assert payload_letters(data_payload(pull_kind(server, "data"))) == "12345"
    pull_kind(server, "end-of-message")
    require_their_state(server, "DONE")
    reply = require_send_bytes(send_event(server, make_data(b"abcde")))
    require_our_state(server, "SEND_BODY")
    send_completed_eom(server)
    require_our_state(server, "DONE")
    feed_ok(client, reply)
    assert payload_as_bytes(pull_kind(client, "data")) == b"abcde"
    pull_kind(client, "end-of-message")
    require_both_done(client)
    require_both_done(server)
    print("zero-info cycle both DONE", flush=True)


def test_informational_keeps_server_in_send_response():
    _client, server, _req = bodied_get_pair()
    encoded_info = require_send_bytes(
        send_event(server, make_informational(100, headers=[]))
    )
    after_info = require_our_state(server, "SEND_RESPONSE")
    print(
        f"informational encoded_len={len(encoded_info)} state={after_info!r}",
        flush=True,
    )
    assert encoded_info
    assert after_info == named_state("SEND_RESPONSE")
    encoded_final = require_send_bytes(
        send_event(server, make_response(200, headers=[("Content-Length", "5")]))
    )
    after_final = require_our_state(server, "SEND_BODY")
    print(
        f"final 200 encoded_len={len(encoded_final)} state={after_final!r}",
        flush=True,
    )
    assert encoded_final
    assert after_final == named_state("SEND_BODY")
    assert after_info != after_final


def test_two_informational_responses_stay_in_send_response():
    _client, server, _req = bodied_get_pair()
    require_send_bytes(send_event(server, make_informational(100, headers=[])))
    require_our_state(server, "SEND_RESPONSE")
    second = runtime_informational_status()
    assert 100 <= second < 200
    assert second not in (100, 101, 102, 199)
    require_send_bytes(
        send_event(server, make_informational(second, headers=[]))
    )
    require_our_state(server, "SEND_RESPONSE")
    require_send_bytes(
        send_event(server, make_response(200, headers=[("Content-Length", "5")]))
    )
    require_our_state(server, "SEND_BODY")


def test_data_events_stay_in_send_body_then_eom_is_done():
    client, server, _req = bodied_get_pair()
    require_send_bytes(
        send_event(server, make_response(200, headers=[("Content-Length", "5")]))
    )
    after_resp = require_our_state(server, "SEND_BODY")
    assert after_resp == named_state("SEND_BODY")
    require_send_bytes(send_event(client, make_data(b"12345")))
    after_client_data = require_our_state(client, "SEND_BODY")
    assert after_client_data == named_state("SEND_BODY")
    send_completed_eom(client)
    after_client_eom = require_our_state(client, "DONE")
    assert after_client_eom == named_state("DONE")
    assert after_client_data != after_client_eom
    require_send_bytes(send_event(server, make_data(b"xyzwv")))
    after_server_data = require_our_state(server, "SEND_BODY")
    assert after_server_data == named_state("SEND_BODY")
    send_completed_eom(server)
    after_server_eom = require_our_state(server, "DONE")
    print(
        f"client after data={after_client_data!r} after eom={after_client_eom!r} "
        f"server after data={after_server_data!r} after eom={after_server_eom!r}",
        flush=True,
    )
    assert after_server_eom == named_state("DONE")
    assert after_server_data != after_server_eom


# ---------------------------------------------------------------------------
# B. Server response from IDLE without a request
# ---------------------------------------------------------------------------


def test_server_408_from_idle_encodes_without_request():
    server = server_connection()
    require_our_state(server, "IDLE")
    require_their_state(server, "IDLE")
    encoded = require_send_bytes(
        send_event(
            server,
            make_response(408, headers=[("Connection", "close")]),
        )
    )
    print(f"408 first={encoded_first_line(encoded)!r}", flush=True)
    assert encoded_status_code(encoded) == 408
    require_our_state(server, "SEND_BODY")
    send_completed_eom(server)
    require_our_state(server, "MUST_CLOSE")
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_runtime_final_response_from_idle_encodes():
    server = server_connection()
    status = runtime_final_not_408()
    assert status != 408
    encoded = require_send_bytes(
        send_event(server, make_response(status, headers=[]))
    )
    assert encoded_status_code(encoded) == status
    require_our_state(server, "SEND_BODY")


# ---------------------------------------------------------------------------
# C. Keep-alive iff HTTP/1.1 and no close token
# ---------------------------------------------------------------------------


def test_http11_without_close_ends_done_and_reuse_works():
    client, server, resp = complete_empty_http11_cycle(host="a", target="/")
    require_no_close_token(resp)
    assert not connection_has_close_token(resp)
    require_our_state(client, "DONE")
    require_their_state(client, "DONE")
    done_our, done_their = connection_side_states(client)
    assert done_our == named_state("DONE")
    assert done_their == named_state("DONE")
    require_start_succeeded(start_next_cycle(client), client)
    require_start_succeeded(start_next_cycle(server), server)
    client_our, client_their = connection_side_states(client)
    server_our, server_their = connection_side_states(server)
    print(
        f"after start client={client_our!r}/{client_their!r} "
        f"server={server_our!r}/{server_their!r}",
        flush=True,
    )
    assert client_our == named_state("IDLE")
    assert client_their == named_state("IDLE")
    assert server_our == named_state("IDLE")
    assert server_their == named_state("IDLE")


def test_comma_list_close_token_disables_keepalive():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(
        client,
        host="a",
        extra_headers=[("Connection", "a, b, cLOse, foo")],
    )
    require_our_state(client, "MUST_CLOSE")
    pull_empty_request(server, raw)
    resp = server_send_status(server, 200, headers=[])
    require_close_token(resp)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_must_close(client)
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(client), client)
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_runtime_comma_list_close_token_disables_keepalive():
    host = runtime_host()
    token = runtime_token()
    value = f"ClOsE, {token}, other"
    print(f"runtime Connection list={value!r}", flush=True)
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(
        client,
        host=host,
        extra_headers=[("Connection", value)],
    )
    require_our_state(client, "MUST_CLOSE")
    pull_empty_request(server, raw)
    resp = server_send_status(server, 200, headers=[])
    require_close_token(resp)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_must_close(client)
    require_local_cycle_refusal(start_next_cycle(client), client)


def test_close_substring_in_other_token_does_not_disable_keepalive():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(
        client,
        host="a",
        extra_headers=[("Connection", "keep-alive, enclosed")],
    )
    after_request = require_our_state(client, "DONE")
    assert after_request == named_state("DONE")
    pull_empty_request(server, raw)
    resp = server_send_status(server, 200, headers=[])
    require_no_close_token(resp)
    assert not connection_has_close_token(resp)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_done(client)
    require_both_done(server)
    done_our, done_their = connection_side_states(client)
    assert done_our == named_state("DONE")
    assert done_their == named_state("DONE")
    require_start_succeeded(start_next_cycle(client), client)
    require_start_succeeded(start_next_cycle(server), server)
    idle_our, idle_their = connection_side_states(client)
    print(
        f"substring Connection still DONE then IDLE our={idle_our!r} "
        f"their={idle_their!r}",
        flush=True,
    )
    assert idle_our == named_state("IDLE")
    assert idle_their == named_state("IDLE")


def test_request_connection_close_echoed_on_204():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(
        client,
        host="a",
        extra_headers=[("Connection", "close")],
    )
    require_our_state(client, "MUST_CLOSE")
    pull_empty_request(server, raw)
    resp = server_send_status(server, 204, headers=[])
    require_close_token(resp)
    assert encoded_status_code(resp) == 204
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_must_close(client)
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(client), client)
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_request_connection_close_echoed_on_non_204():
    status = runtime_final_not_204_or_200()
    assert status not in (200, 204)
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(
        client,
        host="a",
        extra_headers=[("Connection", "close")],
    )
    require_our_state(client, "MUST_CLOSE")
    pull_empty_request(server, raw)
    resp = server_send_status(server, status, headers=[])
    require_close_token(resp)
    assert encoded_status_code(resp) == status
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_must_close(client)
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_http10_get_adds_close_on_bare_200():
    server = server_connection()
    feed_ok(server, b"GET / HTTP/1.0\r\n\r\n")
    req = pull_kind(server, "request")
    assert request_method(req) == b"GET"
    assert request_target(req) == b"/"
    assert event_version(req) == b"1.0"
    pull_kind(server, "end-of-message")
    resp = server_send_status(server, 200, headers=[])
    require_close_token(resp)
    assert encoded_status_code(resp) == 200
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_runtime_http10_get_target_adds_close():
    target = runtime_target()
    assert target != "/"
    server = server_connection()
    feed_ok(server, f"GET {target} HTTP/1.0\r\n\r\n".encode("ascii"))
    req = pull_kind(server, "request")
    assert request_target(req) == target.encode("ascii")
    pull_kind(server, "end-of-message")
    resp = server_send_status(server, 200, headers=[])
    require_close_token(resp)
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_http10_response_disables_reuse():
    client, _raw = client_sent_named_get(host="a", target="/")
    feed_ok(client, b"HTTP/1.0 200 \r\nContent-Length: 0\r\n\r\n")
    pulled = pull_kind(client, "response")
    assert event_version(pulled) == b"1.0"
    pull_kind(client, "end-of-message")
    require_our_state(client, "MUST_CLOSE")
    require_local_cycle_refusal(start_next_cycle(client), client)


def test_http10_keep_alive_token_does_not_enable_reuse():
    server = server_connection()
    feed_ok(server, b"GET / HTTP/1.0\r\nConnection: keep-alive\r\n\r\n")
    pull_kind(server, "request")
    pull_kind(server, "end-of-message")
    resp = server_send_status(server, 200, headers=[])
    require_close_token(resp)
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(server), server)


def test_http10_response_keep_alive_token_does_not_enable_reuse():
    client, _raw = client_sent_named_get(host="a", target="/")
    feed_ok(
        client,
        b"HTTP/1.0 200 \r\nConnection: keep-alive\r\nContent-Length: 0\r\n\r\n",
    )
    pulled = pull_kind(client, "response")
    assert event_version(pulled) == b"1.0"
    pull_kind(client, "end-of-message")
    require_our_state(client, "MUST_CLOSE")
    require_local_cycle_refusal(start_next_cycle(client), client)


def test_server_set_close_disables_keepalive():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(client, host="a", target="/")
    pull_empty_request(server, raw)
    resp = server_send_status(server, 200, headers=[("Connection", "close")])
    require_close_token(resp)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_must_close(client)
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(client), client)
    require_local_cycle_refusal(start_next_cycle(server), server)

    neighbor_client, neighbor_server, neighbor_resp = complete_empty_http11_cycle(
        host="a", target="/"
    )
    require_no_close_token(neighbor_resp)
    require_both_done(neighbor_client)
    require_start_succeeded(start_next_cycle(neighbor_client), neighbor_client)
    require_start_succeeded(start_next_cycle(neighbor_server), neighbor_server)


# ---------------------------------------------------------------------------
# D. Start next cycle from both DONE
# ---------------------------------------------------------------------------


def test_start_next_cycle_from_both_done_returns_idle_and_delete_404_runs():
    client, server, first_resp = complete_empty_http11_cycle(host="a", target="/")
    require_both_done(client)
    require_both_done(server)
    idle = named_state("IDLE")
    done = named_state("DONE")
    before_client = connection_side_states(client)
    before_server = connection_side_states(server)
    print(
        f"before start client={before_client!r} server={before_server!r}",
        flush=True,
    )
    assert before_client == (done, done)
    assert before_server == (done, done)
    assert before_client[0] != idle
    assert before_server[0] != idle
    started_client = start_next_cycle(client)
    started_server = start_next_cycle(server)
    print(
        f"start client exc="
        f"{type(started_client.exception).__name__ if started_client.exception else None} "
        f"server exc="
        f"{type(started_server.exception).__name__ if started_server.exception else None}",
        flush=True,
    )
    require_start_succeeded(started_client, client)
    require_start_succeeded(started_server, server)
    after_client = connection_side_states(client)
    after_server = connection_side_states(server)
    print(
        f"after start client={after_client!r} server={after_server!r}",
        flush=True,
    )
    assert started_client.exception is None
    assert started_server.exception is None
    assert after_client == (idle, idle)
    assert after_server == (idle, idle)
    assert after_client != before_client
    assert after_server != before_server
    assert after_client[0] != done
    assert after_server[0] != done
    delete = client_send_empty(
        client, method="DELETE", target="/foo", host="a"
    )
    pulled = pull_empty_request(server, delete)
    assert request_method(pulled) == b"DELETE"
    assert request_target(pulled) == b"/foo"
    resp = server_send_status(server, 404, headers=[])
    assert encoded_status_code(resp) == 404
    assert encoded_status_code(resp) != encoded_status_code(first_resp)
    feed_ok(client, resp)
    second = pull_kind(client, "response")
    assert status_code(second) == 404
    pull_kind(client, "end-of-message")
    require_both_done(client)
    require_both_done(server)
    second_done_client = connection_side_states(client)
    second_done_server = connection_side_states(server)
    print(
        f"DELETE/404 second cycle client={second_done_client!r} "
        f"server={second_done_server!r}",
        flush=True,
    )
    assert second_done_client == (done, done)
    assert second_done_server == (done, done)
    assert second_done_client != after_client
    assert second_done_server != after_server


def test_peer_http_version_still_present_after_next_cycle():
    server = server_connection()
    assert peer_http_version(server) is None
    client, raw = client_sent_named_get(host="a", target="/")
    feed_ok(server, raw)
    pulled = pull_kind(server, "request")
    assert event_version(pulled) == b"1.1"
    recorded = peer_http_version(server)
    print(f"peer version after first pull={recorded!r}", flush=True)
    assert recorded == b"1.1"
    pull_kind(server, "end-of-message")
    resp = send_final_200(server)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_start_succeeded(start_next_cycle(server), server)
    after = peer_http_version(server)
    print(f"peer version after start={after!r}", flush=True)
    assert after == recorded
    assert after is not None


def test_runtime_second_cycle_after_start():
    host = runtime_host()
    target = runtime_target()
    method = second_request_method()
    second_target = runtime_target()
    print(
        f"runtime cycle1 host={host!r} target={target!r} "
        f"cycle2 method={method} target={second_target!r}",
        flush=True,
    )
    client, server, _resp = complete_empty_http11_cycle(host=host, target=target)
    require_start_succeeded(start_next_cycle(client), client)
    require_start_succeeded(start_next_cycle(server), server)
    raw = client_send_empty(
        client, method=method, target=second_target, host=host
    )
    pulled = pull_empty_request(server, raw)
    assert request_method(pulled) == method.encode("ascii")
    assert request_target(pulled) == second_target.encode("ascii")


# ---------------------------------------------------------------------------
# E. Client cannot pipeline
# ---------------------------------------------------------------------------


def test_client_second_request_before_response_pulled_is_local_error():
    client = client_connection()
    client_send_empty(client, host="a", target="/")
    method = second_request_method()
    assert method not in ("GET", "DELETE")
    refused = send_event(
        client,
        make_request(method=method, target="/x", headers=[("Host", "a")]),
    )
    require_local_refusal(refused)
    print(f"second {method} before response pulled refused", flush=True)

    neighbor, server, _resp = complete_empty_http11_cycle(host="a", target="/")
    require_start_succeeded(start_next_cycle(neighbor), neighbor)
    require_start_succeeded(start_next_cycle(server), server)
    encoded = require_send_bytes(
        send_event(
            neighbor,
            make_request(method=method, target="/x", headers=[("Host", "a")]),
        )
    )
    print(f"same {method} after start encoded_len={len(encoded)}", flush=True)
    assert encoded


def test_client_second_request_after_done_without_start_is_local_error():
    client, _server, _resp = complete_empty_http11_cycle(host="a", target="/")
    method = second_request_method()
    assert method not in ("GET", "DELETE")
    refused = send_event(
        client,
        make_request(method=method, target="/x", headers=[("Host", "a")]),
    )
    require_local_refusal(refused)

    neighbor, server, _ok = complete_empty_http11_cycle(host="a", target="/")
    require_start_succeeded(start_next_cycle(neighbor), neighbor)
    require_start_succeeded(start_next_cycle(server), server)
    encoded = require_send_bytes(
        send_event(
            neighbor,
            make_request(method=method, target="/x", headers=[("Host", "a")]),
        )
    )
    print(
        f"after DONE without start refused; after start len={len(encoded)}",
        flush=True,
    )
    assert encoded


def test_client_second_request_succeeds_after_start():
    client, server, _resp = complete_empty_http11_cycle(host="a", target="/")
    require_start_succeeded(start_next_cycle(client), client)
    require_start_succeeded(start_next_cycle(server), server)
    encoded = require_send_bytes(
        send_event(
            client,
            make_request(method="DELETE", target="/foo", headers=[("Host", "a")]),
        )
    )
    print(f"public DELETE after start first={encoded_first_line(encoded)!r}", flush=True)
    assert b"DELETE" in encoded_first_line(encoded)
    assert b"/foo" in encoded_first_line(encoded)


def test_client_third_request_without_second_start_is_local_error():
    client, server, _resp = complete_empty_http11_cycle(host="a", target="/")
    require_start_succeeded(start_next_cycle(client), client)
    require_start_succeeded(start_next_cycle(server), server)
    delete = client_send_empty(
        client, method="DELETE", target="/foo", host="a"
    )
    pull_empty_request(server, delete)
    resp = server_send_status(server, 404, headers=[])
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_done(client)
    require_both_done(server)
    method = second_request_method()
    refused = send_event(
        client,
        make_request(method=method, target="/third", headers=[("Host", "a")]),
    )
    require_local_refusal(refused)

    n_client, n_server, _ok = complete_empty_http11_cycle(host="a", target="/")
    require_start_succeeded(start_next_cycle(n_client), n_client)
    require_start_succeeded(start_next_cycle(n_server), n_server)
    delete2 = client_send_empty(
        n_client, method="DELETE", target="/foo", host="a"
    )
    pull_empty_request(n_server, delete2)
    resp2 = server_send_status(n_server, 404, headers=[])
    feed_ok(n_client, resp2)
    pull_response_then_eom(n_client)
    require_start_succeeded(start_next_cycle(n_client), n_client)
    encoded = require_send_bytes(
        send_event(
            n_client,
            make_request(method=method, target="/third", headers=[("Host", "a")]),
        )
    )
    print(f"third request after second start len={len(encoded)}", flush=True)
    assert encoded


# ---------------------------------------------------------------------------
# F. Server serial pipelining; paused is not need-data
# ---------------------------------------------------------------------------


def test_three_pipelined_gets_are_delivered_one_cycle_at_a_time():
    server = server_connection()
    feed_public_three_gets(server)
    require_paused(pull_next(server))
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    second = pull_kind(server, "request")
    assert request_target(second) == b"/2"
    assert payload_as_bytes(pull_kind(server, "data")) == b"67890"
    pull_kind(server, "end-of-message")
    require_paused(pull_next(server))
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    third = pull_kind(server, "request")
    assert request_target(third) == b"/3"
    pull_kind(server, "end-of-message")
    require_need_data(pull_next(server))
    print("three GETs delivered one cycle at a time", flush=True)


def test_paused_after_first_eom_is_not_need_data():
    server = server_connection()
    feed_public_three_gets(server)
    result = pull_next(server)
    paused = require_paused(result)
    print(f"after /1 paused={paused!r}", flush=True)
    assert paused != need_data_token()
    assert not event_is_kind(paused, "request")


def test_paused_after_response_eom_before_start():
    server = server_connection()
    feed_public_three_gets(server)
    require_paused(pull_next(server))
    send_final_200(server)
    require_our_state(server, "DONE")
    require_paused(pull_next(server))
    print("still paused after 200+EOM before start", flush=True)
    require_start_succeeded(start_next_cycle(server), server)
    second = pull_kind(server, "request")
    assert request_target(second) == b"/2"


def test_feeding_while_paused_does_not_reveal_next_request():
    server = server_connection()
    feed_public_three_gets(server)
    require_paused(pull_next(server))
    extra = b"GET /extra HTTP/1.1\r\nHost: a\r\n\r\n"
    feed_ok(server, extra)
    still = pull_next(server)
    require_paused(still)
    assert not event_is_kind(still.value, "request")
    send_final_200(server)
    require_paused(pull_next(server))
    require_start_succeeded(start_next_cycle(server), server)
    second = pull_kind(server, "request")
    assert request_target(second) == b"/2"
    print("paused feed did not reveal /2; start still yields /2", flush=True)

    incomplete = server_connection()
    feed_ok(incomplete, b"GET /partial HTTP/1.1\r\n")
    require_need_data(pull_next(incomplete))
    feed_ok(incomplete, b"Host: a\r\n\r\n")
    partial = pull_kind(incomplete, "request")
    assert request_target(partial) == b"/partial"


def test_after_third_request_pull_is_need_data():
    server = server_connection()
    feed_public_three_gets(server)
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    second = pull_kind(server, "request")
    assert request_target(second) == b"/2"
    assert payload_as_bytes(pull_kind(server, "data")) == b"67890"
    pull_kind(server, "end-of-message")
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    third = pull_kind(server, "request")
    assert request_target(third) == b"/3"
    pull_kind(server, "end-of-message")
    leftover = require_need_data(pull_next(server))
    print(f"after /3 pull={leftover!r}", flush=True)
    assert leftover == need_data_token()
    assert leftover != paused_result()
    assert not event_is_kind(leftover, "request")


def test_leftover_bytes_after_third_are_paused_in_trailing_data():
    server = server_connection()
    feed_public_three_gets(server)
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    pull_kind(server, "request")
    pull_kind(server, "data")
    pull_kind(server, "end-of-message")
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    third = pull_kind(server, "request")
    assert request_target(third) == b"/3"
    pull_kind(server, "end-of-message")
    require_need_data(pull_next(server))
    leftover = b"GET /4 HTTP/1.1\r\nHost: a\r\n\r\n"
    feed_ok(server, leftover)
    require_paused(pull_next(server))
    held = trailing_held_bytes(server)
    print(f"trailing leftover={held!r}", flush=True)
    assert leftover in held
    further = pull_next(server)
    require_paused(further)
    assert not event_is_kind(further.value, "request")


def test_empty_body_pipelined_second_request_is_paused():
    host = runtime_host()
    first = runtime_target()
    second = runtime_target()
    print(f"empty-body HEAD {first} then {second}", flush=True)
    assert first != "/1" and second != "/2"
    block = (
        f"HEAD {first} HTTP/1.1\r\nHost: {host}\r\n\r\n"
        f"HEAD {second} HTTP/1.1\r\nHost: {host}\r\n\r\n"
    ).encode("ascii")
    server = server_connection()
    feed_ok(server, block)
    req = pull_kind(server, "request")
    assert request_method(req) == b"HEAD"
    assert request_target(req) == first.encode("ascii")
    pull_kind(server, "end-of-message")
    result = pull_next(server)
    require_paused(result)
    assert not event_is_kind(result.value, "request")


def test_runtime_pipelined_targets_are_serialized():
    host = runtime_host()
    t1 = runtime_target()
    t2 = runtime_target()
    t3 = runtime_target()
    body_n = 3 + (runtime_int() % 3)
    if body_n == 5:
        body_n = 4
    body1 = (runtime_token().encode("ascii") * 4)[:body_n]
    body2 = (runtime_token().encode("ascii") * 4)[:body_n]
    print(f"runtime pipeline {t1} {t2} {t3} body_n={body_n}", flush=True)
    cl = str(body_n).encode("ascii")
    block = (
        b"GET "
        + t1.encode("ascii")
        + b" HTTP/1.1\r\nHost: "
        + host.encode("ascii")
        + b"\r\nContent-Length: "
        + cl
        + b"\r\n\r\n"
        + body1
        + b"GET "
        + t2.encode("ascii")
        + b" HTTP/1.1\r\nHost: "
        + host.encode("ascii")
        + b"\r\nContent-Length: "
        + cl
        + b"\r\n\r\n"
        + body2
        + b"GET "
        + t3.encode("ascii")
        + b" HTTP/1.1\r\nHost: "
        + host.encode("ascii")
        + b"\r\n\r\n"
    )
    server = server_connection()
    feed_ok(server, block)
    assert request_target(pull_kind(server, "request")) == t1.encode("ascii")
    assert payload_as_bytes(pull_kind(server, "data")) == body1
    pull_kind(server, "end-of-message")
    require_paused(pull_next(server))
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    assert request_target(pull_kind(server, "request")) == t2.encode("ascii")
    assert payload_as_bytes(pull_kind(server, "data")) == body2
    pull_kind(server, "end-of-message")
    require_paused(pull_next(server))
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    assert request_target(pull_kind(server, "request")) == t3.encode("ascii")
    pull_kind(server, "end-of-message")
    require_need_data(pull_next(server))


# ---------------------------------------------------------------------------
# G. Start-next-cycle refused when a side is not DONE
# ---------------------------------------------------------------------------


def test_start_next_cycle_from_send_body_is_local_error_not_error():
    client, server, _req = bodied_get_pair()
    before = require_our_state(client, "SEND_BODY")
    assert before == named_state("SEND_BODY")
    refused = start_next_cycle(client)
    exc = require_local_cycle_refusal(refused, client)
    local_t = local_protocol_error_type()
    remote_t = remote_protocol_error_type()
    print(
        f"SEND_BODY start exc={type(exc).__name__}",
        flush=True,
    )
    assert refused.exception is exc
    assert isinstance(exc, local_t)
    assert not isinstance(exc, remote_t)
    after_refuse_our, after_refuse_their = connection_side_states(client)
    assert after_refuse_our != named_state("ERROR")
    assert after_refuse_their != named_state("ERROR")
    assert after_refuse_our == named_state("SEND_BODY")
    require_neither_error(client)
    require_our_state(client, "SEND_BODY")
    body = require_send_bytes(send_event(client, make_data(b"12345")))
    send_completed_eom(client)
    feed_ok(server, body)
    pull_kind(server, "data")
    pull_kind(server, "end-of-message")
    resp = require_send_bytes(
        send_event(server, make_response(200, headers=[("Content-Length", "5")]))
    )
    reply = require_send_bytes(send_event(server, make_data(b"abcde")))
    send_completed_eom(server)
    feed_ok(client, resp + reply)
    pull_kind(client, "response")
    pull_kind(client, "data")
    pull_kind(client, "end-of-message")
    require_both_done(client)
    require_start_succeeded(start_next_cycle(client), client)
    idle_our, idle_their = connection_side_states(client)
    print(
        f"later both-DONE start idle our={idle_our!r} their={idle_their!r}",
        flush=True,
    )
    assert idle_our == named_state("IDLE")
    assert idle_their == named_state("IDLE")


def test_start_next_cycle_before_server_done_is_local_error():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(client, host="a", target="/")
    client_done = require_our_state(client, "DONE")
    peer_waiting = require_their_state(client, "SEND_RESPONSE")
    assert client_done == named_state("DONE")
    assert peer_waiting == named_state("SEND_RESPONSE")
    refused = start_next_cycle(client)
    exc = require_local_cycle_refusal(refused, client)
    local_t = local_protocol_error_type()
    remote_t = remote_protocol_error_type()
    print(
        f"client-DONE server-not-DONE start exc={type(exc).__name__}",
        flush=True,
    )
    assert refused.exception is exc
    assert isinstance(exc, local_t)
    assert not isinstance(exc, remote_t)
    after_our, after_their = connection_side_states(client)
    assert after_our != named_state("ERROR")
    assert after_their != named_state("ERROR")
    pull_empty_request(server, raw)
    resp = send_final_200(server)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_done(client)
    require_start_succeeded(start_next_cycle(client), client)
    idle_our, idle_their = connection_side_states(client)
    assert idle_our == named_state("IDLE")
    assert idle_their == named_state("IDLE")


def test_start_next_cycle_on_server_before_response_is_local_error():
    server = server_connection()
    feed_ok(server, b"GET / HTTP/1.1\r\nHost: a\r\n\r\n")
    pulled = pull_kind(server, "request")
    assert request_method(pulled) == b"GET"
    pull_kind(server, "end-of-message")
    waiting = require_our_state(server, "SEND_RESPONSE")
    assert waiting == named_state("SEND_RESPONSE")
    refused = start_next_cycle(server)
    exc = require_local_cycle_refusal(refused, server)
    local_t = local_protocol_error_type()
    remote_t = remote_protocol_error_type()
    print(
        f"server SEND_RESPONSE start exc={type(exc).__name__}",
        flush=True,
    )
    assert refused.exception is exc
    assert isinstance(exc, local_t)
    assert not isinstance(exc, remote_t)
    after_our, after_their = connection_side_states(server)
    assert after_our != named_state("ERROR")
    assert after_their != named_state("ERROR")
    send_final_200(server)
    require_start_succeeded(start_next_cycle(server), server)
    idle_our, idle_their = connection_side_states(server)
    assert idle_our == named_state("IDLE")
    assert idle_their == named_state("IDLE")


def test_start_next_cycle_after_failed_attempt_still_works_when_both_done():
    client = client_connection()
    server = server_connection()
    raw = client_send_empty(client, host="a", target="/")
    refused = start_next_cycle(client)
    exc = require_local_cycle_refusal(refused, client)
    local_t = local_protocol_error_type()
    remote_t = remote_protocol_error_type()
    print(
        f"early start exc={type(exc).__name__}",
        flush=True,
    )
    assert refused.exception is exc
    assert isinstance(exc, local_t)
    assert not isinstance(exc, remote_t)
    after_our, after_their = connection_side_states(client)
    assert after_our != named_state("ERROR")
    assert after_their != named_state("ERROR")
    pull_empty_request(server, raw)
    resp = send_final_200(server)
    feed_ok(client, resp)
    pull_response_then_eom(client)
    require_both_done(client)
    done_our, done_their = connection_side_states(client)
    assert done_our == named_state("DONE")
    assert done_their == named_state("DONE")
    require_start_succeeded(start_next_cycle(client), client)
    idle_our, idle_their = connection_side_states(client)
    print(
        f"failed start left connection usable idle our={idle_our!r} "
        f"their={idle_their!r}",
        flush=True,
    )
    assert idle_our == named_state("IDLE")
    assert idle_their == named_state("IDLE")


def test_start_next_cycle_after_http10_exchange_is_refused():
    server = server_connection()
    feed_ok(server, b"GET / HTTP/1.0\r\n\r\n")
    pull_kind(server, "request")
    pull_kind(server, "end-of-message")
    server_send_status(server, 200, headers=[])
    require_both_must_close(server)
    require_local_cycle_refusal(start_next_cycle(server), server)
    require_our_state(server, "MUST_CLOSE")
    require_their_state(server, "MUST_CLOSE")


# ---------------------------------------------------------------------------
# H. Wrong-role send is a local protocol error
# ---------------------------------------------------------------------------


def test_client_sending_response_is_local_error():
    neighbor = client_connection()
    encoded = require_send_bytes(
        send_event(neighbor, make_request(headers=[("Host", "a")]))
    )
    print(f"client request neighbor len={len(encoded)}", flush=True)
    assert encoded
    client = client_connection()
    require_both_idle(client)
    refused = send_event(client, make_response(200, headers=[]))
    require_local_refusal(refused)


def test_client_sending_response_after_request_is_local_error():
    client = client_connection()
    encoded = require_send_bytes(
        send_event(client, make_request(headers=[("Host", "a")]))
    )
    assert encoded
    after_request = require_our_state(client, "SEND_BODY")
    assert after_request == named_state("SEND_BODY")
    refused = send_event(client, make_response(200, headers=[]))
    exc = require_local_refusal(refused)
    local_t = local_protocol_error_type()
    remote_t = remote_protocol_error_type()
    print(
        f"client response-after-request exc={type(exc).__name__}",
        flush=True,
    )
    assert refused.exception is exc
    assert refused.value is None
    assert isinstance(exc, local_t)
    assert not isinstance(exc, remote_t)


def test_server_sending_request_is_local_error():
    neighbor = server_connection()
    encoded = require_send_bytes(
        send_event(
            neighbor,
            make_response(408, headers=[("Connection", "close")]),
        )
    )
    print(f"server 408 neighbor len={len(encoded)}", flush=True)
    assert encoded
    server = server_connection()
    require_both_idle(server)
    refused = send_event(server, make_request(headers=[("Host", "a")]))
    require_local_refusal(refused)


def test_server_sending_request_after_leave_idle_is_local_error():
    server = server_connection()
    feed_ok(server, b"GET / HTTP/1.1\r\nHost: a\r\n\r\n")
    pulled = pull_kind(server, "request")
    assert request_method(pulled) == b"GET"
    waiting = require_our_state(server, "SEND_RESPONSE")
    assert waiting == named_state("SEND_RESPONSE")
    refused = send_event(server, make_request(headers=[("Host", "a")]))
    exc = require_local_refusal(refused)
    local_t = local_protocol_error_type()
    remote_t = remote_protocol_error_type()
    print(
        f"server request-after-leave-idle exc={type(exc).__name__}",
        flush=True,
    )
    assert refused.exception is exc
    assert refused.value is None
    assert isinstance(exc, local_t)
    assert not isinstance(exc, remote_t)
