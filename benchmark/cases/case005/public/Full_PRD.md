# httpwire — Full Product Requirements Document

## Product overview

**httpwire** is a pure-Python HTTP/1.1 wire protocol library. It implements the first chapter of HTTP/1.1 as specified in RFC 7230 (Message Syntax and Routing): taking bytes on and off the wire, and the headers that control that framing. It does not perform any network I/O of its own. An integrator supplies whatever I/O they already have — synchronous, threaded, asynchronous, or otherwise — and uses httpwire only to turn high-level HTTP events into bytes and bytes back into events.

A first-time integrator creates a connection object in the client role, encodes a GET request for a path such as `/xml` with a Host header, pushes those bytes through their own socket, feeds the reply bytes back into the same connection, and pulls a response event, zero or more data events, and an end-of-message event. A server-role connection is the mirror of that: the events one side encodes are the events the other side pulls. If either side violates HTTP/1.1, the operation does not succeed and the failure is a protocol error.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished httpwire product. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Connection object** | The object that tracks one HTTP/1.1 connection. It is created in either the client role or the server role. It does not open sockets or read from the network. |
| **Event** | A high-level HTTP unit the integrator sends or receives instead of raw bytes. The six event kinds are listed in FP-01. |
| **Request event** | The start of an HTTP request: method, target, headers, and HTTP version. |
| **Informational-response event** | An HTTP 1xx response: status code in the range 100 inclusive to 200 exclusive, headers, HTTP version, and reason phrase. |
| **Response event** | The start of a final HTTP response: status code in the range 200 inclusive to 1000 exclusive, headers, HTTP version, and reason phrase. |
| **Data event** | A piece of a message body. |
| **End-of-message event** | The end of a request or response, optionally carrying trailing headers. |
| **Connection-closed event** | The sending side of this HTTP conversation will send no more data. The receiving side may still be open. |
| **Send operation** | Encode one event into bytes for the integrator to write, and update the connection’s state. A connection-closed event produces no bytes. |
| **Passthrough send** | The send variant that returns a sequence of pieces instead of one concatenated byte string, and that keeps a caller-supplied body placeholder intact so the integrator can hand it to an operating-system sendfile-style write. Specified in FP-03. |
| **Feed received bytes** | Give the connection bytes that just arrived from the peer. This only stores them. |
| **Pull the next event** | Parse one event out of the stored bytes, update state, and return it. |
| **Need-data** | The pull result that means no further real event is available until more bytes are fed. |
| **Paused** | The pull result that means no further real event is available until something else happens (the next cycle is started, or a protocol switch is resolved). Specified in FP-04 and FP-07. |
| **Start the next cycle** | Reset a reusable connection so another request/response can run on it. Specified in FP-04. |
| **Mark send as failed** | Tell the connection that the integrator did not actually transmit the bytes the last send produced. Specified in FP-05. |
| **Client role / server role** | Which side of HTTP this connection is playing. The other side is the peer. |
| **Our state / their state** | The current state-machine state of our role and of the peer’s role. The nine states are enumerated in FP-02. |
| **Local protocol error** | A protocol failure caused by the integrator’s own event or send. It is one of the two concrete kinds of protocol error. |
| **Remote protocol error** | A protocol failure caused by the peer’s bytes. It is the other concrete kind of protocol error. |
| **Suggested status** | An integer on a protocol error suggesting which HTTP status a server might send (or might have sent) for that violation. The default is 400. |
| **Keep-alive** | Reusing one connection for another request/response cycle after both sides reach DONE. Specified in FP-04. |
| **Trailing data** | Bytes that have been fed but not yet parsed, plus whether the receive side has been closed. Specified in FP-07. |
| **Core capability** | A user-observable capability that reflects httpwire’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

httpwire is a **library**. Integrators install the httpwire package and construct connection objects and events in Python. There is no command-line product, no socket layer, and no configuration file of httpwire’s own.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- The six event kinds, their fields, header normalization, and construction-time checks (FP-01).
- A connection object in the client or server role: send encodes events to bytes; feed-then-pull turns bytes into events; both sides of the conversation are tracked; need-data is returned when a pull cannot yet complete (FP-02).
- Body framing through `Content-Length`, `Transfer-Encoding: chunked`, and HTTP/1.0 close-delimited bodies, including the passthrough send for sendfile-style placeholders (FP-03).
- The state machine across a request/response cycle, keep-alive reuse, `Connection: close`, HTTP/1.0 peers, client non-pipelining, and serial server pipelining (FP-04).
- Local versus remote protocol errors, unrecoverable send/receive failure, the incomplete-event size limit, and marking a send as failed (FP-05).
- Half-duplex connection shutdown, clean versus unclean close, and the connection-closed event (FP-06).
- Informational responses, `Expect: 100-continue`, `CONNECT`, and `Upgrade:` protocol switches with trailing data (FP-07).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A pure-Python library with zero runtime third-party dependencies. No compiled extensions, native code, GPU, or accelerator are required or claimed.
- **Language:** Python 3.8 or newer, including the CPython and PyPy implementations the project tests.
- **Platforms:** Intended to work on Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host able to load httpwire from this repository’s source tree and encode then parse one GET request. There is no accelerator profile.
- **I/O:** httpwire contains no I/O. Bytes in and bytes out are the entire interface to the network. A stub that “sends” by writing to a real socket inside the library is not this product.
- **Protocol dialect:** httpwire itself speaks only HTTP/1.1 on the wire. It understands HTTP/1.0 peers when reading. It does not implement HTTP/2.
- **Scope:** RFC 7230 message syntax and routing, plus `Expect: 100-continue` from RFC 7231. Not URL routing, conditional GET, cookie policy, or content negotiation.
- **Error text:** Wording of protocol-error messages is informational. Graded behavior is success versus failure, which kind of protocol error, the suggested status when that status is specified below, and the state the connection is left in — not a particular sentence.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real httpwire behavior matches the described outcomes when a connection is constructed in the named role and events are sent or bytes are fed and pulled.
- **Absent / hollow:** Send always returns the same fixture bytes; pull always returns a hard-coded response; protocol violations are accepted; keep-alive always works or never works; a socket library is required to “round-trip.”

Cheaper proxies (the standard-library HTTP client or server, a regex that splits on blank lines, a hard-coded request/response pair, or a library that performs I/O itself) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces httpwire’s event-to-bytes engine for a core capability.

**Negative control (library substrate):** When httpwire is deliberately not available to an isolated process, constructing a client-role connection and encoding a GET for `/` with Host `example.com` must fail to produce a successful httpwire request encoding — a hard assertion, not a skip. When the interpreter is present and the package is loaded from this tree, that same send yields bytes that a server-role connection can feed and pull back as a GET request for `/` with that Host. Output-equality alone is not proof that the real package ran.

## Non-goals

- Performing any network I/O, TLS, DNS, or URL parsing. Examples in the documentation open sockets themselves; that I/O is not an httpwire capability.
- Replacing an HTTP client such as requests, or a web framework. httpwire is a toolkit for building those things.
- HTTP/2 or HTTP/3.
- Supporting the HTTP/1.0 `Connection: keep-alive` pseudo-standard. An HTTP/1.0 peer always ends the connection after one cycle.
- Transfer encodings other than `chunked`. `gzip` and `deflate` as transfer encodings are refused.
- Generating a table of reason phrases. A caller who wants a reason phrase supplies one; the product does not look one up.
- Preserving chunk-extension metadata. Extensions are parsed and discarded.
- URL routing, authentication, cookies as a policy, caching, or content negotiation.
- Shipping a command-line program, a server binary, or a benchmark as a product surface.
- Treating the documentation build, the fuzzer, or packaging scripts as product capabilities.

---

## Feature points

### FP-01: HTTP events and header normalization

**Public entry:** httpwire’s event constructors, used on their own or as the values passed to the send operation in FP-02. This feature point is what an event looks like and which constructions succeed or fail **before** any connection is involved. Sending those events on a connection, and the bytes that produces, is FP-02. Body-length accounting while sending or receiving is FP-03.

**Normal behavior:**

- There are exactly six event kinds: request, informational-response, response, data, end-of-message, and connection-closed. An observer can tell them apart.
- A request event carries a method, a target, a header list, and an HTTP version. Constructing a GET request for `/` with a Host header of `example.com` succeeds. The default HTTP version is `1.1`. Method, target, and version are stored as byte strings: native text that is ASCII, or a byte buffer, is accepted at construction and becomes bytes. Version numbers are two digits separated by a dot, so a comparison such as “is this version less than `1.1`” is meaningful.
- An HTTP/1.0 request with no Host header succeeds: GET for `/`, empty headers, version `1.0` is a valid request event. An HTTP/1.1 request with a Host header whose name is spelled `hOSt` succeeds; the ordinary header view shows the name as lowercase `host`, and the raw-items view still shows the original `hOSt` spelling.
- An informational-response event constructed with status 100 and an empty header list succeeds. Status is an integer in the range 100 inclusive to 200 exclusive. A response event constructed with status 204, empty headers, and version `1.0` succeeds. Status is an integer in the range 200 inclusive to 1000 exclusive. A status value that is an integer-valued status constant (for example the standard-library “OK” status) is stored as a plain integer. Informational-response and response events also default to HTTP version `1.1`. Both carry a reason phrase that defaults to empty; a caller-supplied reason such as `OK` is stored as a byte string.
- A data event constructed with payload `asdf` stores that payload. An end-of-message event constructed with no arguments has an empty trailing-header list. A connection-closed event has no fields.
- Headers on request, informational-response, response, and end-of-message events are an ordered list of name/value pairs. After construction, each name and each value is a byte string, each name is lowercase, and neither name nor value has leading or trailing whitespace. Native ASCII text and byte-buffer values are accepted at construction. Header order is preserved except for the send-time Host-first rule in FP-02.
- The ordinary header view is the lowercased name paired with the value. A raw-items view on the same header list recovers the original name casing the caller supplied: a request whose headers were `Host=example.org` then `Connection=keep-alive` has ordinary pairs `host` / `example.org` and `connection` / `keep-alive`, and raw items `Host` / `example.org` and `Connection` / `keep-alive`.
- `Content-Length` whose value is the digits `1` is accepted and stored as lowercase `content-length` with value `1`. Two `Content-Length` headers that are both `0`, or a single `Content-Length` whose value is `0 , 0`, collapse to one `content-length` of `0`.
- `Transfer-Encoding` whose value is `chunked`, or `cHuNkEd`, is accepted and stored as lowercase `transfer-encoding` with value `chunked`.
- Header values may contain some non-whitespace control bytes (for example byte 1, byte 2, and byte 127). A Set-Cookie value that contains byte 1 is accepted. Those values are kept as-is.

**Boundary / error behavior:**

- An HTTP/1.1 request with no Host header is refused as a local protocol error. The event is not constructed. The connection, if any, is unaffected.
- A request with two Host headers is refused as a local protocol error, including when the HTTP version is `1.0`.
- A header name with leading or trailing whitespace is refused. A header name containing a space, a NUL, a non-ASCII byte, or a control byte is refused. A header value containing a carriage return, a line feed, a form feed, a vertical tab, or a NUL is refused. A header value with leading or trailing whitespace (space or tab) is refused.
- A request target containing a NUL, a space, byte 127, or byte 238 is refused. A method containing characters that are not a single HTTP method token (for example a string that looks like a whole request line) is refused.
- An informational-response event whose status is 200 is refused. A response event whose status is 100 is refused. A status that is not an integer (for example the text `100`) is refused.
- `Content-Length` whose value is not a decimal integer (`asdf`, `1x`) is refused. Two `Content-Length` headers with different values (`1` and `2`) are refused. A single `Content-Length` whose comma-separated pieces disagree (`1 , 1,2`) is refused. A `Content-Length` whose digit string is longer than 20 digits (for example 21 digits of `1`) is refused. Three `Content-Length` entries that are not all the same value are refused. A second `Transfer-Encoding` header is refused even when both values are `chunked`.
- `Transfer-Encoding` whose value is `gzip`, or `chunked` together with `gzip`, is refused as a local protocol error whose suggested status is 501.

**Verifiable oracle:**

- Success: GET `/` with Host `example.com` constructs a request whose method, target, and version are bytes and whose version defaults to `1.1`; HTTP/1.0 GET `/` with no Host succeeds; `hOSt` is stored as ordinary `host` and raw `hOSt`; informational status 100 succeeds and response status 204 succeeds; both default to version `1.1` and an empty reason; a caller-supplied reason `OK` is stored as bytes; an integer-valued status constant is stored as a plain integer; data payload `asdf` is recovered; end-of-message defaults to no trailing headers; ordinary headers are lowercase byte pairs without surrounding whitespace; raw items keep the caller’s name casing; `Content-Length: 1` and `Transfer-Encoding: cHuNkEd` normalize as above; two `Content-Length: 0` headers become one `0`; a Set-Cookie value containing byte 1 is kept.
- Failure / absence: HTTP/1.1 GET `/` with no Host succeeds; two Host headers succeed; a header name with a trailing space succeeds; a header value containing a line feed, a form feed, or a vertical tab succeeds; informational status 200 succeeds; response status 100 succeeds; `Content-Length: asdf` succeeds; a 21-digit `Content-Length` succeeds; a single `Content-Length` of `1 , 1,2` succeeds; two `Transfer-Encoding: chunked` headers succeed; `Transfer-Encoding: gzip` succeeds or is silently ignored; method, target, and version remain native text instead of bytes; the ordinary header view keeps mixed-case names and there is no way to recover the original casing; a response without a supplied reason invents a phrase such as OK.

---

### FP-02: Bring-your-own-I/O connection

**Public entry:** httpwire’s connection object, constructed in the client role or the server role. The integrator encodes events with the send operation and recovers events by feeding received bytes then pulling the next event. Event shape is FP-01. Body framing rules that decide *how* a body is encoded are FP-03. Which sequences of events are legal across a cycle, and reuse of the connection, are FP-04. Protocol failures are FP-05.

**This feature point uses FP-01.** Every event named here is an event from FP-01.

**Normal behavior:**

- Constructing a connection in the client role records our role as client and the peer role as server. Constructing one in the server role records the reverse. Both sides start in IDLE. Our state, their state, and the pair of states are each queryable. The nine states a side can be in are exactly: IDLE, SEND_RESPONSE, SEND_BODY, DONE, MUST_CLOSE, CLOSED, MIGHT_SWITCH_PROTOCOL, SWITCHED_PROTOCOL, and ERROR.
- Before any request has been seen, a pull on a fresh connection in either role returns need-data. It does not fail.
- A client-role connection that sends a GET request for `/` with Host `example.com` and Content-Length 10 produces a complete HTTP/1.1 request: a request line naming GET and `/` and version 1.1, then the headers, then a blank line. After that send, both the client-role connection and a server-role connection that has been fed those bytes and pulled the request show client state SEND_BODY and server state SEND_RESPONSE. The server-role connection’s record of the peer HTTP version is `1.1`. The client-role connection’s record of the peer HTTP version is still absent.
- Those same bytes, fed to a server-role connection and pulled, yield a request event whose method is GET, target is `/`, Host is `example.com`, and Content-Length is `10`. The events one role sends are the events the other role pulls.
- A server-role connection that then sends an informational-response event with status 100 and empty headers produces a status line for HTTP/1.1 status 100. If the caller did not supply a reason phrase, the encoded status line carries an empty reason (the product does not invent a phrase such as Continue or OK). If the caller supplied a reason, that reason is what is written after the status code. A following response event with status 200 and Content-Length 11 produces a status line for 200 and that header, again with an empty reason unless the caller supplied one. After the response, both sides are in SEND_BODY.
- Sending a data event whose payload is `12345` while Content-Length framing is in effect (FP-03) produces exactly those five bytes. After the last Content-Length bytes have been fed, a pull yields that last data event, and a further pull with no additional feed yields end-of-message. Sending the matching end-of-message event produces no additional bytes when Content-Length is already satisfied. After both sides have sent their end-of-message events, both sides are in DONE.
- Send never writes to a socket. The integrator receives bytes (or no bytes, for a connection-closed event) and is responsible for transmitting them. Feed received bytes never reads from a socket. The two-step receive is required: feeding stores; pulling parses one event. A body may be pulled as several data events when the integrator feeds the body in several pieces. A sender may likewise send several data events for one body.
- When the stored bytes are not yet a complete event, a pull returns need-data and the stored bytes are retained. Feeding another piece and pulling again continues the same event. Concrete case: a client-role connection that has sent a GET for `/xml` with Host `httpbin.org` and is then fed only the first fragment of a 200 response returns need-data; after enough further fragments are fed, a pull returns the response event.
- httpwire itself encodes only HTTP/1.1. A request or response event whose HTTP version is not `1.1` cannot be sent (FP-05). A peer’s HTTP/1.0 request or response can still be pulled: feeding a server-role connection the bytes of `GET / HTTP/1.0` with no headers yields a request event with version `1.0` and an end-of-message event (no body; see FP-03).
- When encoding a request, the Host header is written before every other header, even if it was not first in the caller’s header list. A request whose headers were `foo=bar` then `Host=example.com` encodes with Host first, then foo.
- When encoding headers, the original name casing from construction (FP-01 raw items) is what is written. The ordinary lowercased view is not what goes on the wire.
- Received header blocks that use a lone line feed, or a mix of carriage-return/line-feed and lone line feed, as line endings are accepted. A response status line that omits the reason phrase is accepted and the reason field is empty. A header with an empty value, or a value that is only tabs and spaces, pulls as an empty value. A single-character header value is accepted.
- Obsolete line folding is applied when **reading** headers. A request whose `Some` header is split as `multi-line`, then a continuation line beginning with a space `header`, then a continuation line beginning with a tab `nonsense`, then a continuation line of mixed spaces and tabs `I guess`, pulls as one `Some` value `multi-line header nonsense I guess`. Leading whitespace on each continuation is collapsed to a single space. A header that is the last header may also be folded.
- After a request has been pulled, the peer HTTP version is retained for the rest of this connection, including after the next cycle is started (FP-04).

**Boundary / error behavior:**

- Constructing a connection with a role that is neither client nor server is refused. No connection object is produced.
- A continuation line that appears where a new header name should start (a folded line as the first header) is refused when pulled, as a remote protocol error. A header name with trailing spaces or a trailing tab before the colon is refused. A header line with no name before the colon is refused.
- Garbage after the request line, after the response line, or a NUL inside a header value is refused when pulled. A request target containing a NUL, a space, byte 127, or byte 238 is refused when pulled.
- Bytes that cannot be a request or response even before a line ending arrives are refused when pulled. Concrete cases for a server-role connection: a single NUL, a single space, or the opening bytes of a TLS Client Hello. Concrete cases for a client-role connection that has already sent a request: a single NUL, a single space, or the opening bytes of a TLS Server Hello. A server-role connection fed only a blank line is refused. A client-role connection that has sent a request and is then fed only a blank line is refused.
- Feeding a non-empty chunk after an empty chunk has already been fed (the empty chunk meaning the receive side closed) is refused as a runtime error, not as a protocol error. An observer can tell this failure apart from a local or remote protocol error. Feeding further empty chunks after the first empty chunk is allowed and does not fail.

**Verifiable oracle:**

- Success: client-role and server-role construction records complementary roles and both sides IDLE; a pull on a fresh connection is need-data; client send of GET `/` with Host `example.com` and Content-Length 10 yields bytes that a server-role connection pulls as that same request; after that send, states are client SEND_BODY and server SEND_RESPONSE; informational 100 then response 200 with Content-Length 11 can be sent and pulled, each with an empty reason unless one was supplied; after the last Content-Length body bytes are fed, a further pull yields end-of-message without more bytes; ten body bytes sent as `12345` then `67890` plus end-of-message bring the client to DONE and the server’s matching eleven-byte body plus end-of-message bring both to DONE; send does not itself transmit; a split response feed returns need-data until the response line and headers are complete; HTTP/1.0 GET `/` with no headers pulls as version `1.0` plus end-of-message; Host is encoded before other headers; original header casing is what is encoded; folded `Some` continuations join as `multi-line header nonsense I guess`; mixed line endings on a 200 response pull as that response.
- Failure / absence: the library opens a socket or reads the network itself; send and feed are the same operation; a pull on a fresh connection fails; Host is encoded in caller order after `foo`; HTTP/1.0 cannot be pulled; folded continuation lines are rejected or kept as separate headers; a TLS Client Hello is accepted as a request; a role other than client or server is accepted; feeding bytes after an empty end-of-receive feed succeeds.

---

### FP-03: Message body framing

**Public entry:** The same send, passthrough send, feed, and pull operations as FP-02, once a request or response has put that side into SEND_BODY. Which framing applies is chosen from the request or response headers (and, for responses, from the request method and the peer’s HTTP version). Event construction rules for those headers are FP-01.

**Normal behavior:**

- On a **request**, the framing is:
  - No `Content-Length` and no `Transfer-Encoding`: empty body, equivalent to Content-Length 0. Sending the request and then an end-of-message event produces no extra body bytes for that end-of-message. A server that pulls that request also pulls an end-of-message immediately.
  - `Content-Length` equal to a non-negative integer N: the sender must provide exactly N body bytes across data events. Each data event encodes as its payload with no extra framing. When N bytes have been sent, the matching end-of-message encodes as empty. The peer that pulls observes data whose payloads concatenate to those N bytes, then end-of-message.
  - `Transfer-Encoding: chunked`: the sender may provide any number of body bytes. Each non-empty data event is encoded as one HTTP/1.1 chunk (hexadecimal size, then the payload). An empty data event encodes as no bytes. The end-of-message event encodes as the zero-size final chunk. If that end-of-message carries trailing headers, those headers appear after the zero-size chunk and before the final blank line. The peer that pulls recovers the concatenated payloads and those trailing headers.
- On a **response**, `Content-Length` equal to N is the same as on a request: exactly N bytes, then end-of-message.
- On a **response**, `Transfer-Encoding: chunked`, or neither framing header, are treated as the same choice from the caller’s point of view: a body of not-yet-known length. The product picks the wire form from the peer’s HTTP version:
  - Peer HTTP/1.1: the response is sent with `Transfer-Encoding: chunked` (and without `Content-Length`), and the body is chunked as above.
  - Peer HTTP/1.0, or no request has been seen yet: the response is sent with neither framing header, the body data events encode as raw payloads, end-of-message encodes as empty, and the connection must close afterwards (FP-04, FP-06).
- On the receive side, the same three framings are recovered from the peer’s bytes. A client that has sent a GET, then is fed an HTTP/1.0 200 status line with no framing headers, then body bytes `12345` then `67890`, then an empty chunk, pulls: the response event (version `1.0`), data `12345`, data `67890`, then end-of-message, then connection-closed. That empty chunk is the end of a close-delimited body, not a remote protocol error (contrast FP-05). The client side is then in MUST_CLOSE.
- If a response is constructed with both `Transfer-Encoding: chunked` and `Content-Length`, transfer-encoding wins: Content-Length is not sent, and the body is framed as in the previous bullet.
- These three response situations always have an empty body, regardless of framing headers the caller set: a response to HEAD; a response whose status is 204; a response whose status is 304. Data events are not sent and end-of-message completes an empty body.
- A server answering HEAD with no framing headers uses the same framing headers it would have used for GET: chunked when the peer is HTTP/1.1, and connection-close framing when the peer is HTTP/1.0.
- When pulling a chunked body, each data event is marked so an observer can tell whether it is the first piece of a given chunk, the last piece of that chunk, both, or neither. The product emits at least one data event per received chunk and may emit more than one when the chunk arrives in pieces. Concrete case: feeding a server-role connection a chunked POST whose next chunk is the five bytes `hello` as one piece pulls one data event that is both the start and the end of that chunk; feeding `hel` then `l` then `o` plus the chunk terminator pulls three data events marked start-only, neither, and end-only. These marks are ignored when a data event is sent; they exist on pulled events.
- Chunk extensions on the size line are parsed and discarded. A chunk written as size 5, then an extension `hello=there`, then payload `xxxxx`, pulls as a data event whose payload is `xxxxx` with no extension attached. Extra spaces or tabs between the chunk size and the line ending are accepted.
- The passthrough send of a data event whose payload is a placeholder object with a length, rather than a byte string, returns a sequence that still contains that same placeholder object, plus any framing pieces the chosen framing requires. Concrete cases, after a server has received GET `/` and sent a 200 response: Content-Length 10 and a placeholder of length 10 yields a sequence that is only that placeholder; chunked framing yields a sequence that contains the placeholder among framing pieces, and substituting ten `x` bytes for the placeholder produces a well-formed chunk whose payload is those ten bytes; HTTP/1.0 close-delimited framing yields a sequence that is only that placeholder. After a Content-Length 10 passthrough of a length-10 placeholder, sending end-of-message succeeds (the connection counts those ten bytes as sent).

**Boundary / error behavior:**

- Sending a data event whose payload would exceed the remaining Content-Length is refused as a local protocol error. Sending end-of-message before Content-Length is satisfied is refused as a local protocol error. Sending trailing headers on an end-of-message when the framing is Content-Length or HTTP/1.0 close-delimited is refused as a local protocol error.
- Sending trailing headers on an end-of-message to an HTTP/1.0 peer is refused as a local protocol error even if the caller asked for chunked framing, because the product will not actually use chunked framing for that peer.
- A chunk size whose hexadecimal digit string is longer than 20 characters is refused when pulled. A chunk size containing a NUL is refused. A chunk whose declared size is 3 but whose following two bytes are not a carriage-return/line-feed pair (for example `xxx` then `__`, or `xxx` then a carriage return and `_`, or `xxx` then `_` and a line feed) is refused. These refusals are remote protocol errors when they come from pulled peer bytes.
- Transfer encodings other than `chunked` are refused at event construction (FP-01) and therefore never become a framing mode.

**Verifiable oracle:**

- Success: GET with no framing headers plus end-of-message encodes no body and the peer pulls request then end-of-message; Content-Length 10 on a request, data `12345` then `67890`, then end-of-message, is ten raw bytes and the peer sees those payloads then end-of-message; chunked request data `1234567890` then `abcde` then end-of-message with trailing header `hello=there` is pulled as those two payloads plus that trailing header; a 200 response with no framing headers sent to an HTTP/1.1 GET is pulled as chunked; the same response sent to an HTTP/1.0 GET has no framing headers, raw body bytes, and the server side must close; a client that pulls an HTTP/1.0 200 with no framing headers, then `12345` then `67890`, then an empty chunk, sees those two data events then end-of-message then connection-closed and is in MUST_CLOSE; both `Transfer-Encoding: chunked` and `Content-Length` on a response to HTTP/1.1 become chunked only; HEAD, 204, and 304 complete with an empty body; HEAD to HTTP/1.1 still advertises chunked and HEAD to HTTP/1.0 still advertises close; a five-byte chunk fed whole is one start-and-end data event; a split five-byte chunk is start / middle / end; a chunk extension is discarded and the payload is kept; passthrough of a length-10 placeholder matches the three framing cases above and Content-Length end-of-message then succeeds.
- Failure / absence: a request with no framing headers requires the caller to send a body; Content-Length is not enforced so extra or missing bytes succeed; chunked data is sent raw; a 200 response to HTTP/1.1 with no framing headers is close-delimited; an HTTP/1.0 200 with no framing headers treats the empty feed as a remote protocol error instead of end-of-message then connection-closed; HEAD responses omit the framing headers GET would have used; 204 is given a non-empty body; trailing headers are accepted on a Content-Length body; a malformed chunk terminator is accepted; chunk extensions appear as part of the payload; passthrough concatenates the placeholder into bytes and the original object is gone; `gzip` is treated as a supported transfer encoding.

---

### FP-04: Connection lifecycle, keep-alive, reuse, and pipelining

**Public entry:** The same connection object as FP-02, plus starting the next cycle, plus the queryable states. Framing that interacts with keep-alive (HTTP/1.0 close-delimited responses) is FP-03. Protocol-switch states are refined in FP-07. Close states are refined in FP-06.

**Normal behavior:**

- A client in IDLE may send a request event and then goes to SEND_BODY. A server goes from IDLE to SEND_RESPONSE when that request is sent or pulled. The server in SEND_RESPONSE may send zero or more informational-response events (staying in SEND_RESPONSE) and then one response event, and then goes to SEND_BODY. Each side in SEND_BODY may send data events (staying in SEND_BODY) and then an end-of-message event, and then goes to DONE.
- A server in IDLE may send a response event without any request having arrived (for example status 408 with `Connection: close`). That response is encoded and the server goes to SEND_BODY. This is how a server times out or rejects unparseable input (FP-05) without a request event.
- Keep-alive is enabled when, and only when, both sides speak HTTP/1.1 and neither side has set `Connection: close`. The token `close` is recognized case-insensitively inside a comma-separated Connection value (`a, b, cLOse, foo` disables keep-alive). An HTTP/1.0 request or response disables keep-alive even if Connection does not say close. When keep-alive is disabled, a side that would have entered DONE enters MUST_CLOSE instead.
- If the integrator sets `Connection: close` on a request, the client side becomes MUST_CLOSE after that request’s end-of-message, and a server that then sends a 204 with no Connection header still emits `Connection: close` on that response. Both sides end in MUST_CLOSE.
- When keep-alive is disabled for any reason the product requires (HTTP/1.0 peer, or the rules above), the product adds `Connection: close` to a response the server sends, even if the caller omitted it. A server that pulls `GET / HTTP/1.0` with no headers and then sends a 200 with no headers encodes `Connection: close` on that response.
- When both sides are in DONE, starting the next cycle succeeds and both sides return to IDLE. A second request/response can then run on the same connection. Concrete case: client GET `/` with Host `a` plus end-of-message, server 200 with chunked plus end-of-message, start the next cycle, client DELETE `/foo` with Host `a` plus end-of-message, server 404 with chunked plus end-of-message. The peer HTTP version recorded in FP-02 is still present after the cycle starts.
- As a client, a second request cannot be sent until the next cycle has been started, and the next cycle cannot be started until the server has reached DONE (the full response has been pulled). Client pipelining is not supported.
- As a server, if the client pipelined a second request, the first request is pulled through its end-of-message, then a further pull returns paused and does not parse the second request. After the server sends its response and end-of-message and starts the next cycle, pulls yield the second request. Concrete case: three GET requests for `/1`, `/2`, and `/3` (the first two with Content-Length 5 and bodies `12345` and `67890`) fed in one block to a server-role connection: the first pull sequence is the `/1` request, data `12345`, end-of-message; the next pull is paused; after a 200 plus end-of-message plus start-next-cycle, the `/2` exchange is available; after another cycle start, the `/3` request and end-of-message are available and a pull is need-data (no leftover request). If more bytes then arrive after `/3` is done, a pull is paused and trailing data holds those leftover bytes.
- Starting the next cycle is refused as a local protocol error when either side is not in DONE. The connection remains usable; the integrator may try again later. This refusal does not put the connection into ERROR (contrast FP-05).

**Boundary / error behavior:**

- A client that tries to send a response event is refused as a local protocol error. A server that tries to send a request event is refused as a local protocol error. A client that sends a second request without starting the next cycle is refused as a local protocol error.
- An HTTP/1.0 peer cannot be kept alive. Starting the next cycle after a completed HTTP/1.0 exchange is refused.
- Paused is not need-data: after a pipelined leftover, feeding more bytes does not make the next request appear until the next cycle is started. After a switch (FP-07), paused is permanent for HTTP parsing.

**Verifiable oracle:**

- Success: GET then body then end-of-message then 200 then body then end-of-message walks IDLE → SEND_BODY/SEND_RESPONSE → SEND_BODY → DONE on each side; a server 408 from IDLE succeeds with no request; HTTP/1.1 without Connection close, both DONE, start-next-cycle returns both to IDLE and a DELETE/404 cycle runs; `Connection: close` on the request puts the client in MUST_CLOSE and the server’s 204 carries `Connection: close`; HTTP/1.0 GET causes the server’s 200 to carry `Connection: close` and the client side must close; three pipelined GETs on a server are delivered one cycle at a time with paused between them; start-next-cycle while a side is not DONE is refused and the connection is not in ERROR; a client cannot send a second request until the cycle is started.
- Failure / absence: states are not queryable or use a different set than the nine named states; keep-alive works with HTTP/1.0; `Connection: close` is ignored; the server does not echo close when the client asked for it; start-next-cycle works from SEND_BODY; a client can pipeline two requests before reading a response; a server parses the second pipelined request before the first response is finished; start-next-cycle after a failed reuse attempt puts the connection in ERROR.

---

### FP-05: Protocol errors and the incomplete-event size limit

**Public entry:** Event construction (FP-01), send, pull, start-the-next-cycle (FP-04), and mark-send-as-failed. This feature point is how failures are distinguished and what remains possible afterwards: local versus remote protocol errors, suggested status, recoverable construction and start-next-cycle, unrecoverable send and receive, mark-send-as-failed, and the incomplete-event size limit, all specified in this feature's own section (the bullets below). Shutdown that is not a protocol violation is FP-06.

**Normal behavior:**

- Protocol errors come in two concrete kinds that an observer can tell apart: local (the integrator’s event or send violated the protocol) and remote (the peer’s bytes violated the protocol). Both kinds are protocol errors. A local protocol error is not a remote protocol error, and the reverse. Neither is a generic runtime error of the kind used when bytes arrive after the receive side has already been closed (FP-02, FP-06).
- Every protocol error carries a suggested status. The default is 400. Two specified exceptions: a `Transfer-Encoding` other than `chunked` at construction (FP-01) suggests 501; exceeding the incomplete-event size limit (below) suggests 431.
- Constructing an invalid event (FP-01) is a local protocol error and is recoverable: no event is produced, and a later valid construction succeeds. No connection state changes, because no connection was involved.
- Starting the next cycle when the connection is not ready (FP-04) is a local protocol error and is recoverable: the connection stays usable.
- A failed pull because the peer violated the protocol is a remote protocol error and is unrecoverable for receiving. Their state becomes ERROR. Further pulls also fail as remote protocol errors. Send still works: a server-role connection that was fed `gibberish` plus a blank line, failed the pull, and then sends a 400 response with empty headers still encodes that 400 (and, per FP-04, `Connection: close`). Our state is not ERROR in this case.
- A failed send because the integrator violated the protocol is a local protocol error and is unrecoverable for sending. Our state becomes ERROR. Further sends also fail as local protocol errors. Their state is not ERROR. Concrete case: sending a request or response whose HTTP version is `1.0` fails (httpwire only sends HTTP/1.1); after that failure, a version-`1.1` event that would have succeeded on a fresh connection also fails.
- Marking a send as failed puts our state in ERROR and leaves their state unchanged, except that if their side was already DONE it becomes MUST_CLOSE. Doing it twice in a row has the same result. After this, send fails as a local protocol error. This is how an integrator tells httpwire that the bytes from a previous send never went out (for example a cancelled upload), so the connection must not be returned to a keep-alive pool (FP-04).
- The connection is constructed with an incomplete-event size limit. The default is 16 kibibytes. The limit is judged against an unfinished request or response line plus headers, not against a complete body that has already been framed. A pull that would have to keep an unfinished request or response line plus headers past the limit fails as a remote protocol error with suggested status 431, and their state becomes ERROR.
- Concrete size cases, server role: feeding `GET / HTTP/1.0` and a `Big` header whose value is 4000 `a` characters, then the header terminator, succeeds when the limit is 5000 and pulls that request plus end-of-message; the same header fails the pull when the limit is 4000. Feeding an endless `Endless` header in 1024-byte `a` pieces eventually fails the pull. A complete request with `Content-Length: 10000` followed by ten thousand `a` body bytes succeeds even when the limit is 5000, because the oversized part is a complete body, not an incomplete header event. Two pipelined GET requests plus a thousand extra `X` bytes succeed against a limit of 100: the first request is pulled, the leftover stays paused (FP-04), and after the response and the next cycle the second request is pulled; a further cycle start that then tries to parse the leftover `X` bytes as a new request fails as a remote protocol error because the incomplete event is still over the limit.
- A receive-side close in the middle of a Content-Length or chunked body is a remote protocol error, not a clean connection-closed event (FP-06). After a POST with Content-Length 100 of which only five bytes `12345` arrived, feeding an empty chunk and pulling fails as a remote protocol error; an observer can tell the failure is about a short body (five bytes received, one hundred expected). After a chunked POST whose current chunk is incomplete, feeding an empty chunk and pulling likewise fails as a remote protocol error. An HTTP/1.0 close-delimited body (no Content-Length, no chunked framing) is the opposite case: the empty chunk ends the body, and the pull yields end-of-message then connection-closed (FP-03).
- A receive-side close in the middle of a request line (server fed `GET /` then an empty chunk) is a remote protocol error.

**Boundary / error behavior:**

- A local protocol error and a remote protocol error are distinguishable from each other and from success and from the runtime error used for “bytes after end-of-receive.” A stub that raises one generic error for every failure does not implement these kinds.
- ERROR cannot be left. There is no operation that returns a side from ERROR to IDLE, DONE, or any other state.
- Send after a remote receive error still works, so a server can answer 400. Receive after a local send error is not required to work beyond what the peer has already sent; the graded obligation is that send itself remains failed.

**Verifiable oracle:**

- Success: HTTP/1.1 GET without Host is a local protocol error at construction and a later valid request still constructs; start-next-cycle before DONE is a local protocol error and a later valid start (after both DONE) still works; `gibberish` plus a blank line is a remote protocol error, their state is ERROR, our state is not, a further pull fails, and a server can still send 400; sending HTTP/1.0 puts our state in ERROR and a subsequent valid send fails; mark-send-as-failed puts our state in ERROR and a following send fails; default incomplete-event limit is 16 kibibytes; a 4000-`a` header succeeds at limit 5000 and fails at limit 4000; a 10000-byte complete body succeeds at limit 5000; pipelined leftovers over the limit fail only when that next message is actually parsed; a Content-Length 100 body cut off after five bytes is a remote protocol error, not connection-closed; an HTTP/1.0 close-delimited body ended by an empty chunk is end-of-message then connection-closed, not a remote protocol error; Transfer-Encoding `gzip` suggests 501; oversize unfinished headers suggest 431.
- Failure / absence: every failure is the same exception kind; a receive error also forbids send so a server cannot answer 400; a send error is recoverable by sending again; mark-send-as-failed is ignored and the connection can be reused; the incomplete-event limit is absent so an endless header is buffered forever; a short body is reported as a clean connection-closed event; suggested status is missing or always 400.

---

### FP-06: Connection shutdown

**Public entry:** Sending or pulling a connection-closed event, and feeding an empty chunk to mean the receive side ended. Keep-alive transitions into MUST_CLOSE are FP-04. Unexpected close in the middle of a body is a remote protocol error in FP-05.

**Normal behavior:**

- A connection-closed event means this party will not send more HTTP data. It does not by itself mean the party cannot still receive. Sending a connection-closed event updates state and produces no bytes.
- Feeding an empty chunk means the peer has closed their sending side. A pull then yields a connection-closed event when that close is legal in the current state (below). Once a connection-closed event has been pulled, further pulls also yield a connection-closed event. Feeding further empty chunks remains allowed.
- Either role in IDLE may send connection-closed. That side becomes CLOSED and the other side becomes MUST_CLOSE. Concrete case: a fresh client sends connection-closed; the client side is CLOSED and the server side is MUST_CLOSE. The peer can then pull connection-closed (repeatedly) and may itself send connection-closed; both sides end in CLOSED. The same walk works with the roles reversed: a fresh server sending connection-closed puts the server side in CLOSED and the client side in MUST_CLOSE.
- A client that has finished its request (DONE or already CLOSED after a half-close) while the server is still in SEND_RESPONSE has closed only its sending side. The server can still send the response. Concrete case: client GET `/foo` with Host `a` plus end-of-message plus connection-closed; states are client CLOSED and server SEND_RESPONSE.
- After a full request and a full response, either side may send connection-closed. The other side becomes MUST_CLOSE if it was in DONE. Sending connection-closed when already CLOSED is allowed and does not fail (it is idempotent).
- A server that must close (MUST_CLOSE) — for example after an HTTP/1.0 exchange (FP-03, FP-04) — sends connection-closed to enter CLOSED.
- A server can finish pipelined requests that arrived before the client half-closed. Concrete case: two GET requests for `/1` and `/2` with five-byte bodies, then an empty feed; the server pulls `/1` and its body, responds, starts the next cycle, then pulls `/2`, its body, and connection-closed; after the second 200 the server is in MUST_CLOSE and sending connection-closed reaches CLOSED.

**Boundary / error behavior:**

- A server that has received a complete request and is in SEND_RESPONSE cannot send connection-closed. That send is a local protocol error. A client that pulls an empty feed in that situation sees a remote protocol error, not a clean connection-closed event.
- A client (or server) in the middle of a Content-Length body cannot send connection-closed. That send is a local protocol error. The peer that is fed an empty chunk instead of the rest of the body sees a remote protocol error (FP-05).
- Feeding a non-empty chunk after the receive side has already been closed is a runtime error, not a protocol error (FP-02).
- Receiving new request bytes while the peer is in MUST_CLOSE is a remote protocol error.

**Verifiable oracle:**

- Success: sending connection-closed from a fresh client puts client CLOSED and server MUST_CLOSE and produces no bytes; sending connection-closed from a fresh server puts server CLOSED and client MUST_CLOSE; the peer can pull connection-closed more than once; both sides sending connection-closed end in CLOSED; a client half-close after a finished GET leaves the server in SEND_RESPONSE so the response can still be sent; connection-closed after both DONE is legal and idempotent; two pipelined GETs plus an empty feed let the server answer both and then close; a server in SEND_RESPONSE cannot send connection-closed; a client in the middle of a ten-byte body cannot send connection-closed; new request bytes while the peer is in MUST_CLOSE are a remote protocol error.
- Failure / absence: connection-closed is required to produce bytes on the wire; a half-close shuts down both directions so the server cannot respond; close in SEND_RESPONSE is accepted; close in the middle of a body is accepted as a clean end-of-message; pulling connection-closed once then pulling again fails or returns need-data; the runtime error for bytes-after-EOF cannot be told apart from a protocol error.

---

### FP-07: Informational responses, 100-continue, and protocol switching

**Public entry:** The same connection object as FP-02, plus the waiting-for-100-continue flags, plus trailing data. Informational-response events are defined in FP-01. Paused as a flow-control result is introduced in FP-04. This feature point is the 1xx / Expect / CONNECT / Upgrade behavior that those earlier points do not specify.

**Normal behavior:**

- A server in SEND_RESPONSE may send one or more informational-response events before the final response event. A client that has sent a request pulls those informational-response events and remains able to send the request body. After a 100 informational-response, the client is no longer waiting for 100-continue (below). After any informational-response or any final response, the waiting flag is off.
- When a client sends a request that includes `Expect: 100-continue` (case-insensitive) and an HTTP version of `1.1` and a non-empty body (a positive Content-Length such as Content-Length 100, or the `Transfer-Encoding: chunked` framing already specified for requests in FP-03), both connections report that the client is waiting for 100-continue. The server-role connection also reports that *they* (the peer) are waiting for 100-continue. The client-role connection does not report that the peer is waiting (the peer is the server). The flag is on after the request is sent or pulled and before any of the following: the server sends a 100 informational-response; the server sends a final response (for example 200); the client sends a data event; or, on that chunked request, the client sends an end-of-message with no preceding data event.
- An `Expect: 100-continue` header on an HTTP/1.0 request does not put the connection into the waiting state.
- Two kinds of switch proposal exist, and they follow the same pattern. The client proposes; the server accepts or denies; on denial, HTTP/1.1 continues; on acceptance, both sides enter SWITCHED_PROTOCOL and httpwire stops parsing HTTP.
  - `CONNECT` to a target such as `example.com:443`: acceptance is a response event whose status is in the 2xx range; denial is a non-2xx response (for example 404).
  - `Upgrade:` with a value such as `a, b`: acceptance is an informational-response event whose status is 101; denial is a normal final response (for example 200).
  - A request may propose both. The server accepts at most one: a 2xx response accepts CONNECT; a 101 informational-response accepts Upgrade.
- The client must finish the proposing request (data and end-of-message) before switch-related state appears. After that end-of-message, the client side is in MIGHT_SWITCH_PROTOCOL. A server-role pull at that moment is paused (the server has not yet accepted or denied).
- On denial, both sides go to ordinary post-response states (client DONE, server SEND_BODY, then DONE after end-of-message). Starting the next cycle is then allowed, and another HTTP request can run.
- On acceptance, both sides are in SWITCHED_PROTOCOL. Further pulls return paused. The send operation refuses further HTTP events as a local protocol error. Bytes that arrive after the accepting response are not parsed as HTTP; they accumulate in trailing data. Concrete case: after acceptance, feeding `123` then `456` leaves trailing data as the six bytes `123456` and a flag that the receive side is still open; pulls remain paused.
- Trailing data is a pair: the unparsed bytes, and a flag that is true when an empty chunk has been fed (receive side closed). While paused for a switch proposal, feeding an empty chunk sets that flag to true and the pull stays paused. After a denial, an empty feed is then pulled as a connection-closed event (FP-06). After an acceptance, an empty feed still leaves the pull paused (the close is for the new protocol, not for HTTP).
- A server that is paused in MIGHT_SWITCH_PROTOCOL because leftover bytes arrived may deny the switch, finish the HTTP response, start the next cycle, and then pull those leftover bytes as a new HTTP request. Concrete case: leftover bytes that are themselves `GET / HTTP/1.0` with no headers become that request plus end-of-message after denial and the next cycle.
- A client in MIGHT_SWITCH_PROTOCOL cannot send another request. That send is a local protocol error.

**Boundary / error behavior:**

- Status 101 is an informational-response event, not a final response event. Status 200 on CONNECT is a final response event. Using the wrong event kind for that status is already refused by FP-01.
- SWITCHED_PROTOCOL is permanent for this connection object. There is no start-next-cycle out of it. The integrator abandons the connection object and uses the socket for the new protocol, reading any leftover bytes from trailing data.
- Paused because of a switch proposal, paused because of pipelining (FP-04), and need-data are distinguishable: need-data becomes a real event after more bytes of the *current* HTTP message; pipelining paused becomes a real event after the next cycle; switch paused either becomes HTTP again after a denial plus the next cycle, or stays paused forever after acceptance.

**Verifiable oracle:**

- Success: a 100 informational-response can be sent after a request and pulled by the client before the final 200; `Expect: 100-continue` on an HTTP/1.1 Content-Length 100 GET sets the client-waiting flag on both connections and the they-are-waiting flag only on the server, and a 100, a 200, or the client sending `12345` each clears those flags; the same Expect header on an HTTP/1.1 chunked request likewise sets those flags, and the client sending end-of-message with no preceding data event then clears them; the same Expect header on HTTP/1.0 does not set the flags; CONNECT plus a 404 plus end-of-message allows the next cycle; CONNECT plus a 200 puts both sides in SWITCHED_PROTOCOL, further HTTP sends fail, pulls are paused, and fed `123`+`456` appear as trailing data; Upgrade plus 101 behaves the same as CONNECT-accepted; Upgrade plus 200 behaves as a denial; leftover `GET / HTTP/1.0` after a denial and the next cycle pulls as that request; an empty feed while might-switch is paused stays paused with the receive-closed flag set, and after denial that empty feed is a connection-closed event.
- Failure / absence: informational-response events cannot be sent; Expect is ignored so the they-are-waiting flag is never on; CONNECT 200 is treated as an ordinary reusable HTTP response; 101 does not stop HTTP parsing and the next bytes are parsed as a request; trailing data is not available so leftover bytes after a switch are lost; a denial forbids reuse; HTTP/1.0 Expect sets the waiting flags; paused and need-data cannot be told apart.
