# feature: F09
"""Acceptance tests for the Model Context Protocol server over stdio (FP-09).

Public entry: the ``membundle mcp`` command. Observations go through sealed
``workspace`` / ``mcp_batch`` (via F09 ``mcp_script``) and on-disk files
the tests wrote. These tests do not import Go packages and do not use
``membundle show`` / ``membundle create`` / ``membundle validate`` as the MCP oracle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from _harness import (
    MCP_ROOT_ENV,
    path_is_dir,
    path_is_file,
    read_file,
    rpc_notification,
    rpc_request,
    utc_today_iso,
    workspace,
)
from F01_helpers import split_yaml_frontmatter
from F03_helpers import (
    mcp_is_invalid_params,
    mcp_is_protocol_error,
    mcp_is_tool_error,
    mcp_reply_for_id,
    path_tokens_for,
    record_string_values,
    unique_tokens,
)
from F04_helpers import (
    compact_token,
    hit_identities,
    identity_in_records,
    numbered_identities,
    require_mcp_empty_success,
    require_mcp_search_success,
    search_concept_spec,
    write_concepts_later_first,
    write_equal_score_title_bundle,
)
from F05_helpers import (
    SEED_LOG_DATE,
    assert_concept_written,
    assert_creation_bullet,
    assert_parent_listing,
    concept_file,
    concept_filename,
    generated_by_and_at,
    parent_index_path,
    seed_bundle,
)
from F06_helpers import (
    assert_concept_updated,
    assert_listing_follows_description,
    assert_update_bullet,
    seed_updatable_concept,
)
from F07_helpers import (
    assert_no_reciprocal_on_target,
    assert_relative_link_to_target,
    seed_relatable_pair,
)
from F08_helpers import (
    assert_both_pass,
    assert_conformant_gate_fail,
    assert_identity_listed,
    assert_numbers_later_greater,
    assert_report_differs_after_strip,
    fact_concept,
    require_mcp_validate_report,
    seed_drift_bundle,
    seed_fact_identities,
    seed_validatable_bundle,
    utc_yesterday,
)
from F09_helpers import (
    SIX_TOOL_NAMES,
    assert_initialize_advertises_tools_resources_prompts,
    assert_json_arrays_empty,
    assert_outside_root_remainder_distinct,
    assert_request_reply_count,
    assert_token_absent_from_batch,
    classify_search,
    classify_validate,
    listed_tool_names,
    mcp_script,
    path_covariates,
    require_empty_ping,
    require_initialize_handshake,
    require_rpc_error_code,
    require_search_hits_identity,
    require_some_rpc_error_code,
    require_tool_error_not_protocol,
    require_tool_success,
    tools_call_params_line,
    tools_call_request,
)


def _kb() -> str:
    return unique_tokens("kb")[0]


def _abs_under(ws, rel: str | Path) -> str:
    """Absolute path of *rel* under the workspace. Omit-bundle joins a relative started path onto the workspace root, so started-path omit-bundle arms pass this spelling."""
    return str((ws.path / rel).resolve())


def _result_of(reply: dict) -> object:
    if mcp_is_protocol_error(reply):
        raise AssertionError(
            f"JSON-RPC protocol error is not a success result; reply={reply!r}"
        )
    if "result" not in reply:
        raise AssertionError(f"success reply has no result member: {reply!r}")
    return reply.get("result")


# ---------------------------------------------------------------------------
# A. Handshake over stdio
# ---------------------------------------------------------------------------


def test_initialize_returns_protocol_version_and_server_identity():
    """Initialize result contains 2024-11-05, membundle-agent-memory, and advertises tools, resources, and prompts (L271, L279)."""
    with workspace() as ws:
        batch = mcp_script(ws, [rpc_request("ping", id=2)])
        init = mcp_reply_for_id(batch, 1)
        result = require_initialize_handshake(init)
        assert_initialize_advertises_tools_resources_prompts(result)
        ping = mcp_reply_for_id(batch, 2)
        require_empty_ping(ping)
        print("initialize handshake literals and capability names present", flush=True)


def test_initialized_cancel_and_ping_notifications_produce_no_response():
    """Initialized, cancel, and ping-without-id add zero stdout lines (L271, L275)."""
    with workspace() as ws:
        batch = mcp_script(
            ws,
            [
                rpc_notification("notifications/initialized"),
                rpc_notification("notifications/cancelled"),
                rpc_notification("ping"),
                rpc_request("ping", id=2),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_empty_ping(mcp_reply_for_id(batch, 2))
        assert_request_reply_count(batch, (1, 2))
        print("notifications including ping-without-id are silent", flush=True)


def test_ping_replies_with_empty_result():
    """Request-form ping has a present result whose leftover walk is empty; initialize still has the two tokens (L271)."""
    with workspace() as ws:
        batch = mcp_script(
            ws,
            [
                rpc_notification("notifications/initialized"),
                rpc_request("ping", id=2),
            ],
        )
        init_result = require_initialize_handshake(mcp_reply_for_id(batch, 1))
        ping = mcp_reply_for_id(batch, 2)
        assert "result" in ping, (
            "ping reply has no present result member; a ping that only "
            f"echoes the request id is not an empty result; reply={ping!r}"
        )
        ping_result = require_empty_ping(ping)
        values = record_string_values(init_result)
        assert "2024-11-05" in values and "membundle-agent-memory" in values
        print(
            f"ping present empty result={ping_result!r} vs initialize tokens",
            flush=True,
        )


# ---------------------------------------------------------------------------
# B. Tools / resources / prompts lists
# ---------------------------------------------------------------------------


def test_tools_list_is_exactly_the_six_named_tools():
    """tools/list identities are exactly the six named MCP tools (L61, L271, L280)."""
    with workspace() as ws:
        batch = mcp_script(ws, [rpc_request("tools/list", id=2)])
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        listed = mcp_reply_for_id(batch, 2)
        names = listed_tool_names(_result_of(listed))
        assert names == SIX_TOOL_NAMES, (
            "tools/list is not exactly the six named tools; "
            f"names={sorted(names)!r} expected={sorted(SIX_TOOL_NAMES)!r}"
        )
        print(f"tools/list names={sorted(names)}", flush=True)


def test_resources_list_and_prompts_list_are_empty_collections():
    """resources/list and prompts/list succeed with a length-0 collection; tools/list is not (L271)."""
    with workspace() as ws:
        batch = mcp_script(
            ws,
            [
                rpc_request("tools/list", id=2),
                rpc_request("resources/list", id=3),
                rpc_request("prompts/list", id=4),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        tools = mcp_reply_for_id(batch, 2)
        resources = mcp_reply_for_id(batch, 3)
        prompts = mcp_reply_for_id(batch, 4)
        tool_names = listed_tool_names(_result_of(tools))
        assert tool_names == SIX_TOOL_NAMES
        resource_lengths = assert_json_arrays_empty(_result_of(resources))
        prompt_lengths = assert_json_arrays_empty(_result_of(prompts))
        assert resource_lengths, (
            "resources/list success result contains no collection of length 0"
        )
        assert prompt_lengths, (
            "prompts/list success result contains no collection of length 0"
        )
        assert all(length == 0 for length in resource_lengths), (
            "resources/list reachable collection is not empty; "
            f"lengths={resource_lengths!r}"
        )
        assert all(length == 0 for length in prompt_lengths), (
            "prompts/list reachable collection is not empty; "
            f"lengths={prompt_lengths!r}"
        )
        print(
            f"resources/prompts empty collections lengths="
            f"{resource_lengths!r}/{prompt_lengths!r}; tools list non-empty",
            flush=True,
        )


def test_tools_list_unchanged_after_create():
    """After membundle_create, tools/list is still the six names; no unmatched-id messages (L271)."""
    with workspace() as ws:
        ident, typ, title, desc, body = unique_tokens(
            "id", "typ", "ttl", "dsc", "bod"
        )
        ident = f"decisions/{ident}"
        rel = _kb()
        seed_bundle(ws, rel)
        batch = mcp_script(
            ws,
            [
                rpc_request("tools/list", id=2),
                tools_call_request(
                    "membundle_create",
                    {
                        "concept_id": ident,
                        "type": typ,
                        "title": title,
                        "description": desc,
                        "body": body,
                        "bundle": rel,
                    },
                    request_id=3,
                ),
                rpc_request("tools/list", id=4),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        first = listed_tool_names(_result_of(mcp_reply_for_id(batch, 2)))
        require_tool_success(mcp_reply_for_id(batch, 3))
        second = listed_tool_names(_result_of(mcp_reply_for_id(batch, 4)))
        assert first == second == SIX_TOOL_NAMES
        assert_request_reply_count(batch, (1, 2, 3, 4))
        print("tools/list unchanged after create; no extra messages", flush=True)


# ---------------------------------------------------------------------------
# C. JSON-RPC protocol errors
# ---------------------------------------------------------------------------


def test_non_json_line_is_parse_error_minus_32700_and_ping_still_works():
    """A non-JSON line is −32700; ping after it is still an empty success (L275, L279)."""
    with workspace() as ws:
        batch = mcp_script(
            ws,
            [
                "this is not json",
                rpc_request("ping", id=2),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_some_rpc_error_code(batch, -32700)
        require_empty_ping(mcp_reply_for_id(batch, 2))
        print("parse error −32700 then ping still works", flush=True)


def test_unknown_method_with_id_is_minus_32601():
    """Unknown method on a request with an id is −32601; ping on the same batch is not (L275)."""
    with workspace() as ws:
        method = unique_tokens("meth")[0]
        batch = mcp_script(
            ws,
            [
                rpc_request(method, id=2),
                rpc_request("ping", id=3),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        unknown = mcp_reply_for_id(batch, 2)
        require_rpc_error_code(unknown, -32601)
        ping = mcp_reply_for_id(batch, 3)
        require_empty_ping(ping)
        print("unknown method with id is −32601", flush=True)


def test_unknown_method_notification_produces_no_reply():
    """Unknown-method notification is silent; the request form of that method is −32601 (L275)."""
    with workspace() as ws:
        method = unique_tokens("nmeth")[0]
        batch = mcp_script(
            ws,
            [
                rpc_request(method, id=2),
                rpc_notification(method),
                rpc_request("ping", id=3),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_rpc_error_code(mcp_reply_for_id(batch, 2), -32601)
        require_empty_ping(mcp_reply_for_id(batch, 3))
        assert_request_reply_count(batch, (1, 2, 3))
        print("unknown-method notification adds zero lines", flush=True)


def test_tools_call_array_string_or_omitted_params_is_minus_32602():
    """tools/call params as array, string, or omitted are −32602; object params are not (L275, L279)."""
    with workspace() as ws:
        ident, typ, title, desc, body, term = unique_tokens(
            "id", "typ", "ttl", "dsc", "bod", "q"
        )
        rel = _kb()
        seed_bundle(
            ws,
            rel,
            [
                search_concept_spec(
                    ident,
                    concept_type=typ,
                    title=title,
                    description=desc,
                    body=f"{body}\n",
                )
            ],
        )
        batch = mcp_script(
            ws,
            [
                tools_call_params_line(request_id=2, shape="array"),
                tools_call_params_line(request_id=3, shape="string"),
                tools_call_params_line(request_id=4, shape="omitted"),
                tools_call_request(
                    "membundle_search",
                    {"query": title, "bundle": rel},
                    request_id=5,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        for rid in (2, 3, 4):
            reply = mcp_reply_for_id(batch, rid)
            require_rpc_error_code(reply, -32602)
            assert mcp_is_invalid_params(reply)
            assert not mcp_is_tool_error(reply)
        live = mcp_reply_for_id(batch, 5)
        assert not mcp_is_invalid_params(live), (
            "object-params tools/call was −32602; live twin must not be that code; "
            f"reply={live!r}"
        )
        records = require_mcp_search_success(classify_search(batch, 5))
        assert identity_in_records(records, ident)
        print("array/string/omitted params are −32602; object params are not", flush=True)


# ---------------------------------------------------------------------------
# D. tools/call dispatch: create, show, search, validate
# ---------------------------------------------------------------------------


def test_create_then_show_search_validate_round_trip():
    """membundle_create then show/search/validate; actor agent/mcp; bookkeeping (L32, L271, L281)."""
    with workspace() as ws:
        ident, typ, title, desc, body = unique_tokens(
            "id", "typ", "ttl", "dsc", "bod"
        )
        ident = f"decisions/{ident}"
        rel = _kb()
        root = seed_bundle(ws, rel)
        before = utc_today_iso()
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_validate", {"bundle": rel}, request_id=2
                ),
                tools_call_request(
                    "membundle_create",
                    {
                        "concept_id": ident,
                        "type": typ,
                        "title": title,
                        "description": desc,
                        "body": body,
                        "bundle": rel,
                    },
                    request_id=3,
                ),
                tools_call_request(
                    "membundle_show",
                    {"concept_id": ident, "bundle": rel},
                    request_id=4,
                ),
                tools_call_request(
                    "membundle_search",
                    {"query": title, "bundle": rel},
                    request_id=5,
                ),
                tools_call_request(
                    "membundle_validate", {"bundle": rel}, request_id=6
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        empty_payload = require_mcp_validate_report(classify_validate(batch, 2))
        require_tool_success(mcp_reply_for_id(batch, 3))
        show_payload, show_text = require_tool_success(mcp_reply_for_id(batch, 4))
        show_values = record_string_values(show_payload)
        assert ident in show_values, (
            f"show payload has no exact identity value {ident!r}; "
            f"values={sorted(show_values)!r}"
        )
        assert typ in show_values, (
            f"show payload has no exact type value {typ!r}; "
            f"values={sorted(show_values)!r}"
        )
        assert any(body in item for item in show_values) or body in show_text, (
            f"show payload has no body token {body!r}; "
            f"values={sorted(show_values)!r} text={show_text!r}"
        )
        records = require_mcp_search_success(classify_search(batch, 5))
        assert identity_in_records(records, ident)
        after_payload = require_mcp_validate_report(classify_validate(batch, 6))
        assert_numbers_later_greater(empty_payload, after_payload)
        assert_concept_written(
            concept_file(root, ident),
            concept_type=typ,
            generated_by="agent/mcp",
            title=title,
            description=desc,
            body_token=body,
        )
        filename = concept_filename(ident)
        assert_parent_listing(
            parent_index_path(root, ident),
            filename=filename,
            title=title,
            description=desc,
        )
        after = utc_today_iso()
        assert_creation_bullet(
            root / "log.md",
            identity=ident,
            filename=filename,
            today=before,
            title=title,
            path_tokens=path_tokens_for(rel, ws.path),
            allowed_dates=frozenset({before, after}),
        )
        print(f"create/show/search/validate round-trip ident={ident!r}", flush=True)


# ---------------------------------------------------------------------------
# E. Update bookkeeping, relate link, actor agent/mcp
# ---------------------------------------------------------------------------


def test_update_and_relate_use_agent_mcp_and_write_bookkeeping_and_relative_link():
    """membundle_update refreshes listing+log with agent/mcp; membundle_relate writes a relative link (L271)."""
    with workspace() as ws:
        (
            upd_id,
            typ,
            title,
            old_desc,
            new_desc,
            body,
            src_id,
            tgt_id,
            src_typ,
            tgt_typ,
            src_title,
            tgt_title,
            src_body,
            tgt_body,
            prose,
        ) = unique_tokens(
            "uid",
            "utyp",
            "uttl",
            "uold",
            "unew",
            "ubod",
            "sid",
            "tid",
            "styp",
            "ttyp",
            "sttl",
            "tttl",
            "sbod",
            "tbod",
            "prose",
        )
        upd_id = f"decisions/{upd_id}"
        src_id = f"architecture/{src_id}"
        tgt_id = f"architecture/{tgt_id}"
        rel_u, rel_r = unique_tokens("kbu", "kbr")
        seed_at = "2020-01-01T00:00:00Z"
        uroot = seed_updatable_concept(
            ws,
            rel_u,
            upd_id,
            concept_type=typ,
            title=title,
            description=old_desc,
            body=body,
            generated_at=seed_at,
        )
        rroot = seed_relatable_pair(
            ws,
            rel_r,
            src_id,
            tgt_id,
            source_type=src_typ,
            source_title=src_title,
            source_body=src_body,
            target_type=tgt_typ,
            target_title=tgt_title,
            target_body=tgt_body,
            generated_at=seed_at,
        )
        before = datetime.now(timezone.utc)
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_update",
                    {
                        "concept_id": upd_id,
                        "description": new_desc,
                        "bundle": rel_u,
                    },
                    request_id=2,
                ),
                tools_call_request(
                    "membundle_relate",
                    {
                        "source_id": src_id,
                        "target_id": tgt_id,
                        "description": prose,
                        "bundle": rel_r,
                    },
                    request_id=3,
                ),
            ],
        )
        after = datetime.now(timezone.utc)
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_tool_success(mcp_reply_for_id(batch, 2))
        require_tool_success(mcp_reply_for_id(batch, 3))
        mapping, _body = assert_concept_updated(
            concept_file(uroot, upd_id),
            concept_type=typ,
            generated_by="agent/mcp",
            seed_generated_at=seed_at,
            before=before,
            after=after,
            title=title,
            description=new_desc,
            body_token=body,
        )
        assert generated_by_and_at(mapping)[0] == "agent/mcp"
        filename = concept_filename(upd_id)
        assert_listing_follows_description(
            parent_index_path(uroot, upd_id),
            identity=upd_id,
            filename=filename,
            new_description=new_desc,
            old_description=old_desc,
            title=title,
        )
        today = utc_today_iso()
        assert_update_bullet(
            uroot / "log.md",
            identity=upd_id,
            filename=filename,
            today=today,
            title=title,
            path_tokens=path_covariates(rel_u, ws.path, uroot),
            allowed_dates=frozenset({today}),
            older_date=SEED_LOG_DATE,
        )
        source_path = concept_file(rroot, src_id)
        target_path = concept_file(rroot, tgt_id)
        assert_relative_link_to_target(
            source_path, src_id, tgt_id, link_text=tgt_title
        )
        assert_no_reciprocal_on_target(target_path, tgt_id, src_id)
        src_mapping, _src_body = split_yaml_frontmatter(read_file(source_path))
        by, _at = generated_by_and_at(src_mapping)
        assert by == "agent/mcp", f"relate source generated.by is {by!r}"
        print("update listing+log and relate relative link with agent/mcp", flush=True)


# ---------------------------------------------------------------------------
# F. Search limits default 10 and max 100
# ---------------------------------------------------------------------------


def test_mcp_search_omit_limit_caps_at_10():
    """Fifteen keyword matches, MCP limit omitted, returns 10 identities not 15 (L271)."""
    with workspace() as ws:
        term = compact_token("m15")
        ids = numbered_identities(15, compact_token("ms15"))
        rel = _kb()
        write_equal_score_title_bundle(ws, rel, term, ids)
        walk_prefix = list(reversed(ids))[:10]
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search",
                    {"query": term, "bundle": rel},
                    request_id=2,
                )
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        records = require_mcp_search_success(classify_search(batch, 2))
        assert len(records) == 10, (
            f"omit-limit on 15 matches returned {len(records)}, not 10"
        )
        ordered = hit_identities(records, ids)
        assert ordered != walk_prefix, (
            "omit-limit returned the reverse-lex walk-order prefix of 10; "
            f"ordered={ordered!r}"
        )
        print(f"omit-limit caps at 10 ordered={ordered!r}", flush=True)


def test_mcp_search_huge_limit_caps_at_100():
    """120 keyword matches, MCP limit 100000 returns 100; omit-limit on the same 120 is 10 (L271)."""
    with workspace() as ws:
        term = compact_token("m120")
        ids = numbered_identities(120, compact_token("ms120"))
        rel = _kb()
        write_equal_score_title_bundle(ws, rel, term, ids)
        walk_prefix = list(reversed(ids))[:100]
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search",
                    {"query": term, "bundle": rel, "limit": 100000},
                    request_id=2,
                ),
                tools_call_request(
                    "membundle_search",
                    {"query": term, "bundle": rel},
                    request_id=3,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        huge = require_mcp_search_success(classify_search(batch, 2))
        omitted = require_mcp_search_success(classify_search(batch, 3))
        assert len(huge) == 100, f"limit 100000 on 120 returned {len(huge)}"
        assert len(omitted) == 10, f"omit-limit on 120 returned {len(omitted)}"
        huge_ids = hit_identities(huge, ids)
        assert huge_ids != walk_prefix, (
            "max-100 returned the reverse-lex walk-order prefix of 100; "
            f"ordered={huge_ids!r}"
        )
        print("huge limit caps at 100; omit-limit on 120 is 10", flush=True)


# ---------------------------------------------------------------------------
# G. Path-bound search
# ---------------------------------------------------------------------------


def test_mcp_path_bound_search_selects_governing_concept():
    """for_path hits the code_refs concept, not a second concept that only mentions the path (L271)."""
    with workspace() as ws:
        gov_id, other_id, typ, gtitle, otitle, desc, gbody, obody = unique_tokens(
            "gid", "oid", "typ", "gttl", "ottl", "dsc", "gbod", "obod"
        )
        path = f"pkg/{compact_token('p')}/x.go"
        rel = _kb()
        write_concepts_later_first(
            ws,
            rel,
            [
                search_concept_spec(
                    gov_id,
                    concept_type=typ,
                    title=gtitle,
                    description=desc,
                    body=f"{gbody}\n",
                    code_refs=[path],
                ),
                search_concept_spec(
                    other_id,
                    concept_type=typ,
                    title=path,
                    description=desc,
                    body=f"{obody} mentions {path}\n",
                ),
            ],
        )
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search",
                    {"for_path": path, "bundle": rel},
                    request_id=2,
                ),
                tools_call_request(
                    "membundle_search",
                    {"query": path, "bundle": rel},
                    request_id=3,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        path_hits = require_mcp_search_success(classify_search(batch, 2))
        assert identity_in_records(path_hits, gov_id), (
            f"for_path did not return the governing identity {gov_id!r}"
        )
        assert not identity_in_records(path_hits, other_id), (
            "for_path treated a title/body mention as coverage; "
            f"other={other_id!r} hits={path_hits!r}"
        )
        keyword = require_mcp_search_success(classify_search(batch, 3))
        assert identity_in_records(keyword, other_id), (
            "keyword query for the path string did not find the second identity"
        )
        print("for_path is not keyword search of the path string", flush=True)


# ---------------------------------------------------------------------------
# H. Validate MCP defaults
# ---------------------------------------------------------------------------


def test_mcp_validate_default_producer_gate_on_until_strict_false():
    """Two-concept orphans: default MCP gate-fail; strict false both-pass (L271)."""
    with workspace() as ws:
        a, b = unique_tokens("a", "b")
        rel = _kb()
        seed_fact_identities(ws, rel, [a, b])
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_validate", {"bundle": rel}, request_id=2
                ),
                tools_call_request(
                    "membundle_validate",
                    {"bundle": rel, "strict": False},
                    request_id=3,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        default_payload = require_mcp_validate_report(classify_validate(batch, 2))
        off_payload = require_mcp_validate_report(classify_validate(batch, 3))
        assert_conformant_gate_fail(default_payload)
        assert_both_pass(off_payload)
        assert_identity_listed(default_payload, a)
        assert_identity_listed(off_payload, b)
        print("MCP producer gate on until strict false", flush=True)


def test_mcp_validate_drift_always_on_without_failing_gate():
    """Default MCP drift warns vs a matching-listing twin and still both-pass (L271)."""
    with workspace() as ws:
        ident, title, mismatch = unique_tokens("id", "tl", "ms")
        rel_bad, rel_ok = unique_tokens("bd", "ok")
        desc = "Use PKCE"
        listing = "Use PKCE for OAuth2."
        seed_drift_bundle(ws, rel_bad, ident, title, desc, mismatch)
        seed_drift_bundle(ws, rel_ok, ident, title, desc, listing)
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_validate", {"bundle": rel_bad}, request_id=2
                ),
                tools_call_request(
                    "membundle_validate", {"bundle": rel_ok}, request_id=3
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        bad = classify_validate(batch, 2)
        ok = classify_validate(batch, 3)
        bad_payload = require_mcp_validate_report(bad)
        ok_payload = require_mcp_validate_report(ok)
        assert_both_pass(bad_payload)
        assert_both_pass(ok_payload)
        extra = [ident, title, mismatch, desc, listing]
        tokens = path_covariates(ws.path, rel_bad, rel_ok)
        assert_report_differs_after_strip(
            bad.report_text,
            ok.report_text,
            path_tokens=tokens,
            extra_tokens=extra,
        )
        print("MCP drift always on; warning does not fail the gate", flush=True)


def test_mcp_validate_stale_gate_only_when_requested():
    """Yesterday stale_after: default both-pass; stale true gate-fail (L271)."""
    with workspace() as ws:
        ident = unique_tokens("id")[0]
        yesterday = utc_yesterday()
        rel = _kb()
        seed_validatable_bundle(
            ws, rel, [fact_concept(ident, extra={"stale_after": yesterday})]
        )
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_validate", {"bundle": rel}, request_id=2
                ),
                tools_call_request(
                    "membundle_validate",
                    {"bundle": rel, "stale": True},
                    request_id=3,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        omitted = require_mcp_validate_report(classify_validate(batch, 2))
        requested = require_mcp_validate_report(classify_validate(batch, 3))
        assert_both_pass(omitted)
        assert_conformant_gate_fail(requested)
        print("MCP stale gate only when requested", flush=True)


# ---------------------------------------------------------------------------
# I. Search with neither query nor path
# ---------------------------------------------------------------------------


def test_mcp_search_neither_query_nor_path_is_empty_success():
    """MCP search with neither query nor for_path is empty success, not a tool error (L275)."""
    with workspace() as ws:
        ident, typ, title, desc, body = unique_tokens(
            "id", "typ", "ttl", "dsc", "bod"
        )
        rel = _kb()
        seed_bundle(
            ws,
            rel,
            [
                search_concept_spec(
                    ident,
                    concept_type=typ,
                    title=title,
                    description=desc,
                    body=f"{body}\n",
                )
            ],
        )
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search",
                    {"bundle": rel},
                    request_id=2,
                ),
                tools_call_request(
                    "membundle_search",
                    {"query": title, "bundle": rel},
                    request_id=3,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        empty = require_mcp_empty_success(classify_search(batch, 2))
        assert empty == []
        live = require_mcp_search_success(classify_search(batch, 3))
        assert identity_in_records(live, ident)
        neither = mcp_reply_for_id(batch, 2)
        assert not mcp_is_tool_error(neither)
        assert not mcp_is_invalid_params(neither)
        print("neither query nor path is empty success", flush=True)


# ---------------------------------------------------------------------------
# J / K. Unknown tool and missing named bundle
# ---------------------------------------------------------------------------


def test_unknown_tool_name_is_tool_error_not_protocol_error():
    """Unknown tools/call name is a tool error, not −32601/−32602; search still works (L275)."""
    with workspace() as ws:
        ident, typ, title, desc, body, unknown = unique_tokens(
            "id", "typ", "ttl", "dsc", "bod", "unk"
        )
        rel = _kb()
        seed_bundle(
            ws,
            rel,
            [
                search_concept_spec(
                    ident,
                    concept_type=typ,
                    title=title,
                    description=desc,
                    body=f"{body}\n",
                )
            ],
        )
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    unknown,
                    {"bundle": rel},
                    request_id=2,
                ),
                tools_call_request(
                    "membundle_search",
                    {"query": title, "bundle": rel},
                    request_id=3,
                ),
                rpc_request("ping", id=4),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        unknown_reply = mcp_reply_for_id(batch, 2)
        require_tool_error_not_protocol(unknown_reply)
        assert not mcp_is_invalid_params(unknown_reply)
        live = require_mcp_search_success(classify_search(batch, 3))
        assert identity_in_records(live, ident)
        require_empty_ping(mcp_reply_for_id(batch, 4))
        print("unknown tool name is tool error", flush=True)


def test_named_missing_bundle_is_tool_error_not_protocol_error():
    """Named missing inside-root bundle is a tool error, not empty-list success (L275)."""
    with workspace() as ws:
        ident, typ, title, desc, body, missing = unique_tokens(
            "id", "typ", "ttl", "dsc", "bod", "miss"
        )
        rel = _kb()
        seed_bundle(
            ws,
            rel,
            [
                search_concept_spec(
                    ident,
                    concept_type=typ,
                    title=title,
                    description=desc,
                    body=f"{body}\n",
                )
            ],
        )
        batch = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search",
                    {"query": title, "bundle": missing},
                    request_id=2,
                ),
                tools_call_request(
                    "membundle_search",
                    {"query": title, "bundle": rel},
                    request_id=3,
                ),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        missing_reply = mcp_reply_for_id(batch, 2)
        require_tool_error_not_protocol(missing_reply)
        assert not mcp_is_invalid_params(missing_reply)
        live = require_mcp_search_success(classify_search(batch, 3))
        assert identity_in_records(live, ident)
        print("named missing bundle is tool error", flush=True)


# ---------------------------------------------------------------------------
# L. Workspace root and path traversal
# ---------------------------------------------------------------------------


def _seed_token_bundle(ws, rel: str, token: str) -> tuple[Path, str]:
    """Bundle whose unique *token* is the concept title. Returns (root, identity)."""
    ident, typ, desc = unique_tokens("id", "typ", "dsc")
    root = seed_bundle(
        ws,
        rel,
        [
            search_concept_spec(
                ident,
                concept_type=typ,
                title=token,
                description=desc,
                body=f"{token}\n",
            )
        ],
    )
    return root, ident


def _confinement_lines(
    *,
    inside_bundle: str,
    missing_rel: str,
    outside_bundle: str,
    unknown_name: str,
    inside_query: str,
    outside_query: str,
    start_id: int = 20,
) -> list:
    return [
        tools_call_request(
            "membundle_search",
            {"query": inside_query, "bundle": inside_bundle},
            request_id=start_id,
        ),
        tools_call_request(
            unknown_name,
            {"bundle": inside_bundle},
            request_id=start_id + 1,
        ),
        tools_call_request(
            "membundle_search",
            {"query": inside_query, "bundle": missing_rel},
            request_id=start_id + 2,
        ),
        tools_call_request(
            "membundle_search",
            {"query": outside_query, "bundle": outside_bundle},
            request_id=start_id + 3,
        ),
    ]


def _assert_confinement_batch(
    batch,
    *,
    inside_ident: str,
    t_out: str,
    strip: list,
) -> None:
    """Live inside arm is a classified hit; outside is unread path-traversal tool error."""
    require_search_hits_identity(batch, 20, inside_ident)
    unknown_reply = mcp_reply_for_id(batch, 21)
    missing_reply = mcp_reply_for_id(batch, 22)
    outside_reply = mcp_reply_for_id(batch, 23)
    require_tool_error_not_protocol(outside_reply)
    require_tool_error_not_protocol(unknown_reply)
    require_tool_error_not_protocol(missing_reply)
    assert_token_absent_from_batch(batch, t_out)
    assert_outside_root_remainder_distinct(
        outside_reply, unknown_reply, missing_reply, strip
    )


def test_membundle_mcp_root_is_workspace_root_and_overrides_started_knowledge():
    """MEMBUNDLE_MCP_ROOT wins over a started knowledge/ parent (L273)."""
    with workspace() as ws:
        t_in, t_out, unknown, missing = unique_tokens("tin", "tout", "unk", "miss")
        root_a = ws.path / unique_tokens("ra")[0]
        root_b = ws.path / unique_tokens("rb")[0]
        inside_rel = f"{root_a.name}/insidekb"
        decoy_rel = f"{root_b.name}/decoykb"
        started = f"{root_b.name}/knowledge"
        _root_in, id_in = _seed_token_bundle(ws, inside_rel, t_in)
        _root_out, id_out = _seed_token_bundle(ws, decoy_rel, t_out)
        _seed_token_bundle(ws, started, unique_tokens("sk")[0])
        inside_abs = str((ws.path / inside_rel).resolve())
        decoy_abs = str((ws.path / decoy_rel).resolve())
        batch = mcp_script(
            ws,
            _confinement_lines(
                inside_bundle=inside_abs,
                missing_rel=missing,
                outside_bundle=decoy_abs,
                unknown_name=unknown,
                inside_query=t_in,
                outside_query=t_out,
            ),
            args=[started],
            env_updates={MCP_ROOT_ENV: str(root_a.resolve())},
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        strip = path_covariates(
            ws.path, root_a, root_b, inside_abs, decoy_abs, inside_rel, decoy_rel, missing
        ) + [unknown, t_in, t_out, id_in, id_out]
        _assert_confinement_batch(
            batch, inside_ident=id_in, t_out=t_out, strip=strip
        )
        twin = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search",
                    {"query": t_out, "bundle": decoy_abs},
                    request_id=2,
                )
            ],
            args=[decoy_rel],
        )
        require_initialize_handshake(mcp_reply_for_id(twin, 1))
        require_search_hits_identity(twin, 2, id_out)
        print("MEMBUNDLE_MCP_ROOT overrides started knowledge parent", flush=True)


def test_started_knowledge_directory_uses_parent_as_workspace_root():
    """Started …/project/knowledge: workspace root is project (L273)."""
    with workspace() as ws:
        t_in, t_out, unknown, missing, t_know = unique_tokens(
            "tin", "tout", "unk", "miss", "tk"
        )
        project = unique_tokens("proj")[0]
        started = f"{project}/knowledge"
        other = f"{project}/otherkb"
        outside = unique_tokens("outp")[0]
        _seed_token_bundle(ws, started, t_know)
        _root_in, id_in = _seed_token_bundle(ws, other, t_in)
        _root_out, id_out = _seed_token_bundle(ws, outside, t_out)
        other_abs = str((ws.path / other).resolve())
        outside_abs = str((ws.path / outside).resolve())
        batch = mcp_script(
            ws,
            _confinement_lines(
                inside_bundle=other_abs,
                missing_rel=missing,
                outside_bundle=outside_abs,
                unknown_name=unknown,
                inside_query=t_in,
                outside_query=t_out,
            ),
            args=[started],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        strip = path_covariates(
            ws.path, project, started, other, other_abs, outside, outside_abs, missing
        ) + [unknown, t_in, t_out, t_know, id_in, id_out]
        _assert_confinement_batch(
            batch, inside_ident=id_in, t_out=t_out, strip=strip
        )
        print("started knowledge/ uses parent as workspace root", flush=True)


def test_started_non_knowledge_path_is_workspace_root():
    """Started path not named knowledge/ is the workspace root (L273)."""
    with workspace() as ws:
        t_in, t_out, unknown, missing = unique_tokens("tin", "tout", "unk", "miss")
        named = unique_tokens("named")[0]
        inside = f"{named}/insidekb"
        outside = unique_tokens("outs")[0]
        _seed_token_bundle(ws, named, unique_tokens("tn")[0])
        _root_in, id_in = _seed_token_bundle(ws, inside, t_in)
        _root_out, id_out = _seed_token_bundle(ws, outside, t_out)
        inside_abs = str((ws.path / inside).resolve())
        outside_abs = str((ws.path / outside).resolve())
        batch = mcp_script(
            ws,
            _confinement_lines(
                inside_bundle=inside_abs,
                missing_rel=missing,
                outside_bundle=outside_abs,
                unknown_name=unknown,
                inside_query=t_in,
                outside_query=t_out,
            ),
            args=[named],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        strip = path_covariates(
            ws.path, named, inside, inside_abs, outside, outside_abs, missing
        ) + [unknown, t_in, t_out, id_in, id_out]
        _assert_confinement_batch(
            batch, inside_ident=id_in, t_out=t_out, strip=strip
        )
        print("started non-knowledge path is workspace root", flush=True)


def test_absolute_bundle_outside_workspace_root_is_tool_error_and_unread():
    """Absolute directory outside the started workspace root is a tool error and unread (L275, L282)."""
    with workspace() as ws:
        t_in, t_out, unknown, missing = unique_tokens("tin", "tout", "unk", "miss")
        named = unique_tokens("nm")[0]
        inside = f"{named}/inkb"
        outside = unique_tokens("abso")[0]
        _seed_token_bundle(ws, named, unique_tokens("tn")[0])
        _root_in, id_in = _seed_token_bundle(ws, inside, t_in)
        _root_out, id_out = _seed_token_bundle(ws, outside, t_out)
        inside_abs = str((ws.path / inside).resolve())
        outside_abs = str((ws.path / outside).resolve())
        batch = mcp_script(
            ws,
            _confinement_lines(
                inside_bundle=inside_abs,
                missing_rel=missing,
                outside_bundle=outside_abs,
                unknown_name=unknown,
                inside_query=t_in,
                outside_query=t_out,
            ),
            args=[named],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        strip = path_covariates(
            ws.path, named, inside, inside_abs, outside, outside_abs, missing
        ) + [unknown, t_in, t_out, id_in, id_out]
        _assert_confinement_batch(
            batch, inside_ident=id_in, t_out=t_out, strip=strip
        )
        twin = mcp_script(
            ws,
            [
                tools_call_request(
                    "membundle_search", {"query": t_out}, request_id=2
                )
            ],
            args=[_abs_under(ws, outside)],
        )
        require_initialize_handshake(mcp_reply_for_id(twin, 1))
        require_search_hits_identity(twin, 2, id_out)
        print("absolute outside bundle is tool error and unread", flush=True)


def test_relative_bundle_escaping_workspace_root_is_tool_error_and_unread():
    """Relative ../outside on a non-knowledge start is a tool error and unread (L273, L275)."""
    with workspace() as ws:
        t_in, t_out, unknown, missing = unique_tokens("tin", "tout", "unk", "miss")
        named = unique_tokens("nmr")[0]
        inside = f"{named}/inkb"
        outside = unique_tokens("relo")[0]
        _seed_token_bundle(ws, named, unique_tokens("tn")[0])
        _root_in, id_in = _seed_token_bundle(ws, inside, t_in)
        _root_out, id_out = _seed_token_bundle(ws, outside, t_out)
        escape = f"../{outside}"
        batch = mcp_script(
            ws,
            _confinement_lines(
                inside_bundle="inkb",
                missing_rel=missing,
                outside_bundle=escape,
                unknown_name=unknown,
                inside_query=t_in,
                outside_query=t_out,
            ),
            args=[named],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        strip = path_covariates(
            ws.path, named, inside, outside, escape, missing
        ) + [unknown, t_in, t_out, id_in, id_out]
        _assert_confinement_batch(
            batch, inside_ident=id_in, t_out=t_out, strip=strip
        )
        print("relative escape is tool error and unread", flush=True)


def test_mcp_started_knowledge_omit_bundle_loads_knowledge_not_parent():
    """membundle mcp …/project/knowledge; omit bundle loads knowledge/, not a parent decoy (L269, L273)."""
    with workspace() as ws:
        t_know, t_parent = unique_tokens("tk", "tp")
        project = unique_tokens("proj")[0]
        started = f"{project}/knowledge"
        parent_decoy = f"{project}/parentkb"
        _root_k, id_know = _seed_token_bundle(ws, started, t_know)
        _seed_token_bundle(ws, parent_decoy, t_parent)
        batch = mcp_script(
            ws,
            [
                tools_call_request("membundle_search", {"query": t_know}, request_id=2),
                tools_call_request("membundle_search", {"query": t_parent}, request_id=3),
            ],
            args=[_abs_under(ws, started)],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_search_hits_identity(batch, 2, id_know)
        empty_parent = require_mcp_empty_success(classify_search(batch, 3))
        assert empty_parent == []
        print("started knowledge omit-bundle loads knowledge not parent", flush=True)


def test_mcp_started_path_is_omit_bundle_default():
    """Started non-knowledge path is the omit-bundle load root (L269, L273)."""
    with workspace() as ws:
        t_named, t_cwd = unique_tokens("tn", "tc")
        named = unique_tokens("nm")[0]
        work = unique_tokens("wd")[0]
        _root_n, id_named = _seed_token_bundle(ws, named, t_named)
        _seed_token_bundle(ws, f"{work}/knowledge", t_cwd)
        cwd = ws.path / work
        assert path_is_dir(cwd / "knowledge")
        batch = mcp_script(
            ws,
            [
                tools_call_request("membundle_search", {"query": t_named}, request_id=2),
                tools_call_request("membundle_search", {"query": t_cwd}, request_id=3),
            ],
            args=[_abs_under(ws, named)],
            cwd=cwd,
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_search_hits_identity(batch, 2, id_named)
        cwd_hits = require_mcp_empty_success(classify_search(batch, 3))
        assert cwd_hits == []
        print("started path is omit-bundle default", flush=True)


def test_mcp_omit_path_follows_cwd_knowledge_default():
    """membundle mcp with no path: omit-bundle follows L49 knowledge/ vs cwd (L49, L269)."""
    with workspace() as ws:
        t_know, t_cwd = unique_tokens("tk", "tc")
        _root_k, id_know = _seed_token_bundle(ws, "knowledge", t_know)
        cwd_ident, cwd_typ, cwd_title, cwd_desc = unique_tokens(
            "cid", "cty", "ctt", "cd"
        )
        seed_bundle(
            ws,
            ".",
            [
                search_concept_spec(
                    cwd_ident,
                    concept_type=cwd_typ,
                    title=t_cwd,
                    description=cwd_desc,
                    body=f"{t_cwd}\n",
                )
            ],
        )
        batch = mcp_script(
            ws,
            [
                tools_call_request("membundle_search", {"query": t_know}, request_id=2),
                tools_call_request("membundle_search", {"query": t_cwd}, request_id=3),
            ],
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_search_hits_identity(batch, 2, id_know)
        cwd_hits = require_mcp_empty_success(classify_search(batch, 3))
        assert cwd_hits == []
        print("omit-path with knowledge/ dir loads knowledge", flush=True)

    with workspace() as ws:
        t_cwd, t_sib = unique_tokens("tc2", "ts2")
        project = unique_tokens("prk")[0]
        sibling = unique_tokens("sibk")[0]
        _root_c, id_cwd = _seed_token_bundle(ws, project, t_cwd)
        _seed_token_bundle(ws, sibling, t_sib)
        cwd = ws.path / project
        ws.write(f"{project}/knowledge", "not-a-directory\n")
        assert path_is_file(cwd / "knowledge")
        batch = mcp_script(
            ws,
            [
                tools_call_request("membundle_search", {"query": t_cwd}, request_id=2),
                tools_call_request("membundle_search", {"query": t_sib}, request_id=3),
            ],
            cwd=cwd,
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        require_search_hits_identity(batch, 2, id_cwd)
        sib_hits = require_mcp_empty_success(classify_search(batch, 3))
        assert sib_hits == []
        print("omit-path with knowledge file loads cwd", flush=True)


def test_omit_path_workspace_root_is_cwd_not_knowledge():
    """membundle mcp with no path: workspace root is cwd; sibling of knowledge/ succeeds (L273)."""
    with workspace() as ws:
        t_sib, t_out, unknown, missing, t_know = unique_tokens(
            "ts", "to", "unk", "miss", "tk"
        )
        project = unique_tokens("pr")[0]
        _seed_token_bundle(ws, f"{project}/knowledge", t_know)
        _root_s, id_sib = _seed_token_bundle(ws, f"{project}/siblingkb", t_sib)
        outside = unique_tokens("outc")[0]
        _root_o, id_out = _seed_token_bundle(ws, outside, t_out)
        cwd = ws.path / project
        sibling_abs = str((cwd / "siblingkb").resolve())
        outside_abs = str((ws.path / outside).resolve())
        batch = mcp_script(
            ws,
            _confinement_lines(
                inside_bundle=sibling_abs,
                missing_rel=missing,
                outside_bundle=outside_abs,
                unknown_name=unknown,
                inside_query=t_sib,
                outside_query=t_out,
            ),
            cwd=cwd,
        )
        require_initialize_handshake(mcp_reply_for_id(batch, 1))
        strip = path_covariates(
            ws.path, project, cwd, sibling_abs, outside, outside_abs, missing
        ) + [unknown, t_sib, t_out, t_know, id_sib, id_out]
        _assert_confinement_batch(
            batch, inside_ident=id_sib, t_out=t_out, strip=strip
        )
        print("omit-path workspace root is cwd, not knowledge/", flush=True)
