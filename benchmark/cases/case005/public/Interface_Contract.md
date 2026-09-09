# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**httpwire** is a pure-Python HTTP/1.1 wire protocol library. It implements the first chapter of HTTP/1.1 as specified in RFC 7230 (Message Syntax and Routing): taking bytes on and off the wire, and the headers that control that framing. It does not perform any network I/O of its own. An integrator supplies whatever I/O they already have — synchronous, threaded, asynchronous, or otherwise — and uses `httpwire` only to turn high-level HTTP events into bytes and bytes back into events.

A first-time integrator creates a connection object in the client role, encodes a `GET` request for a path such as `/xml` with a `Host` header, pushes those bytes through their own socket, feeds the reply bytes back into the same connection, and pulls a response event, zero or more data events, and an end-of-message event. A server-role connection is the mirror of that: the events one side encodes are the events the other side pulls. If either side violates HTTP/1.1, the operation does not succeed and the failure is a protocol error.

The finished product is an **importable Python library**, not a command-line program, not a network service, and not a socket layer. Integrators install the `httpwire` package and construct connection objects and events in Python. There is no product-owned configuration file.

The product is a pure-Python library with zero runtime third-party dependencies. No compiled extension, native code, GPU, or accelerator is required. The language is Python 3.8 or newer, including CPython and PyPy. Platforms are Linux, macOS, and Windows; documented execution is Linux. Hardware is CPU-only.

The library itself speaks only HTTP/1.1 on the wire. It understands HTTP/1.0 peers when reading. It does not implement HTTP/2. Scope is RFC 7230 message syntax and routing, plus `Expect: 100-continue` from RFC 7231. It is not URL routing, TLS, DNS, cookie policy, or content negotiation.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The public surface is the importable package `httpwire`. Callers write `import `httpwire`` or `from `httpwire` import …` and obtain the published entries from that package root. The importable package is a single top-level directory named `httpwire`. Importing the package performs no I/O against caller files, starts no processes, and opens no sockets.

The independently verifiable library entries named from this package root are:

- `Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, `ConnectionClosed` — the six event kinds. Each is a distinguishable callable type. An observer can tell them apart by type identity. Event constructors are used on their own and as the values passed to `send`.
- `Connection` — the object that tracks one HTTP/1.1 connection. It is constructed in the client role or the server role. The published constructor is the role alone, or the role then an integer incomplete-event size limit as a second positional argument. The omitted second argument is 16 kibibytes. There is no setter and no third constructor. It does not open sockets or read from the network.
- `CLIENT` — the client-role value passed to `Connection` as the first positional argument.
- `SERVER` — the server-role value passed to `Connection` as the first positional argument.
- `NEED_DATA` — the pull result when stored bytes are not yet a complete event.
- `PAUSED` — the pull result when no further real event is available until the next cycle is started or a protocol switch is resolved.
- `IDLE`, `SEND_RESPONSE`, `SEND_BODY`, `DONE`, `MUST_CLOSE`, `CLOSED`, `MIGHT_SWITCH_PROTOCOL`, `SWITCHED_PROTOCOL`, `ERROR` — the nine states a side can be in. Each is a package-root export. They are nine distinct objects; no two compare equal.
- `LocalProtocolError` — a protocol failure caused by the integrator’s own event or send. It is a class.
- `RemoteProtocolError` — a protocol failure caused by the peer’s bytes. It is a class. A local protocol error is not also a remote protocol error.

The six event kinds are: request, informational-response, response, data, end-of-message, and connection-closed.

A connection encodes events with `send` and recovers events by `receive_data` then `next_event`. Send never writes to a socket. Feed never reads from a socket. Feeding only stores; pulling parses one event. When the stored bytes are not yet a complete event, a pull returns need-data and the stored bytes are retained. A connection-closed event produces no bytes on send.

The surfaces group as:

- Event shape, header normalization, and construction-time checks, before any connection is involved.
- A connection in the client or server role: send encodes events to bytes; feed-then-pull turns bytes into events; both sides of the conversation are tracked.
- Body framing through `Content-Length`, `Transfer-Encoding: chunked`, and HTTP/1.0 close-delimited bodies, including a passthrough send that keeps a caller-supplied body placeholder intact for a sendfile-style write.
- The state machine across a request/response cycle, keep-alive reuse, `Connection: close`, HTTP/1.0 peers, client non-pipelining, and serial server pipelining.
- Local versus remote protocol errors, unrecoverable send/receive failure, the incomplete-event size limit, and marking a send as failed.
- Half-duplex connection shutdown, clean versus unclean close, and the connection-closed event.
- Informational responses, `Expect: 100-continue`, `CONNECT`, and `Upgrade:` protocol switches with trailing data.

**Not in this surface.** A command-line program, a `python -m` entry, a server binary, or a socket library. Performing TLS, DNS, or URL parsing. HTTP/2 or HTTP/3. Transfer encodings other than `chunked`. Generating a table of reason phrases. Preserving chunk-extension metadata. A configuration-file format of the library’s own.

### Naming conventions

**Product and package.** The product identity is httpwire. The installable distribution name and the importable top-level package are spelled `httpwire`. The importable package directory is `httpwire`.

**Event types.** Published event types use PascalCase: `Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, `ConnectionClosed`. Each is a callable class. Callers construct instances by calling the class.

**Roles and connection.** The client-role token is `CLIENT`. The server-role token is `SERVER`. The connection type is `Connection`.

**Protocol errors.** Published error types use PascalCase: `LocalProtocolError` and `RemoteProtocolError`. Each is a class.

**Event fields.** Stored fields use snake_case: `method`, `target`, `headers`, `http_version` on a request; `status_code`, `reason`, `headers`, `http_version` on informational-response and response; `data` on a data event; `headers` on end-of-message (trailing headers). A connection-closed event has no fields. Connection sides expose `our_state` and `their_state`. The queryable pair is the `states` attribute: a role-keyed mapping or a two-item sequence resolved to client-side then server-side. `our_state` and `their_state` are not a substitute for `states`.

**Header views.** The ordinary header view is the lowercased name paired with the value, read by iterating `headers`. The raw-items view is the callable `raw_items` on that same header container: it recovers the original name casing the caller supplied.

**HTTP version.** Version numbers are two digits separated by a dot, stored as byte strings. The default is `1.1`. The spelling `1.0` is a valid stored version and compares as less than `1.1`.

**Header and framing tokens.** Ordinary header names are lowercase byte strings: `host`, `connection`, `content-length`, `transfer-encoding`. Caller spellings such as `Host`, `hOSt`, `Content-Length`, and `Transfer-Encoding` are accepted at construction; the raw-items view keeps that casing. The only accepted transfer-encoding value is `chunked` (any mix of letter case, stored lowercase). `gzip` and `deflate` as transfer encodings are refused.

**States.** The nine states a side can be in are exactly: `IDLE`, `SEND_RESPONSE`, `SEND_BODY`, `DONE`, `MUST_CLOSE`, `CLOSED`, `MIGHT_SWITCH_PROTOCOL`, `SWITCHED_PROTOCOL`, and `ERROR`. Each is importable as ``httpwire`.<name>` and as `from `httpwire` import <name>`. They are package-root objects, not strings and not values that exist only on a `Connection`.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**No command-line product.** There is no console-script entry and no `python -m` program that is part of this surface. Outcomes are returned or raised from library calls. Library entries do not exit the host process as their success or failure report. There are no product exit codes.

**No I/O.** Bytes in and bytes out are the entire interface to the network. The library does not open sockets, read the network, or write the network. A stub that “sends” by writing to a real socket inside the library is not this product.

**Library substrate.** When the `httpwire` package is not importable, a program that does `import `httpwire``, takes `Request` from that module, and constructs `Request` with `method` `GET`, `target` `/`, and `headers` `[('Host', 'example.com')]` does not run to completion and does not yield a request event. When the package is importable, that same construction succeeds. Output-equality alone is not proof that the real package ran.

**Package identity.** After `import `httpwire``, the module’s `__name__` is a text string. Splitting that string on the period with at most one cut yields a first piece equal to `httpwire`, matching the importable package directory name.

**Events are types.** The six event constructors are six distinct types. A successful construction returns an instance of that constructor. Method, target, and HTTP version are stored as the exact type `bytes` (not a bytearray). Status is stored as the exact type `int` (not an integer-valued status enum). A caller-supplied reason such as `OK` is stored as `bytes`. An omitted reason is empty `bytes`. Native ASCII text and byte buffers are accepted at construction for those byte fields and for header names and values.

**Header list.** Headers on request, informational-response, response, and end-of-message are an ordered list of name/value pairs. After construction, each name and each value is `bytes`, each ordinary name is lowercase, and neither name nor value has leading or trailing whitespace. Caller order is preserved at construction. The raw-items view keeps the caller’s name casing.

**Host rules at construction.** An HTTP/1.1 request requires a `Host` header. An HTTP/1.0 request with no `Host` succeeds. Two `Host` headers are refused, including on HTTP/1.0. A failed event construction produces no event, is a `LocalProtocolError` (not a `RemoteProtocolError`), and leaves any already-created connection’s `our_state` and `their_state` unchanged.

**Suggested status.** Every protocol error carries an integer suggested status. The default is 400. A `Transfer-Encoding` other than `chunked` at construction suggests 501. Exceeding the incomplete-event size limit suggests 431. Wording of protocol-error messages is not a compatibility contract.

**Content-Length.** A decimal digit string of at most 20 digits is accepted. Equal repeats, or comma-separated equal pieces, collapse to one `content-length`. Disagreeing values, non-digits, or more than 20 digits are refused as a local protocol error.

**Transfer-Encoding.** A single `chunked` value (any letter case) is stored as lowercase `chunked`. A second `Transfer-Encoding` header is refused. `gzip`, `deflate`, or `chunked` together with `gzip`, is a local protocol error whose suggested status is 501.

**Wire dialect.** The product encodes only HTTP/1.1. When encoding a request, the `Host` header is written before every other header, even if it was not first in the caller’s list. The original name casing from construction (raw items) is what is written. An HTTP/1.0 peer can still be pulled. An HTTP/1.0 peer always ends the connection after one cycle; the HTTP/1.0 `Connection: keep-alive` pseudo-standard is not supported.

**Need-data and paused.** Need-data means no further real event is available until more bytes are fed. Paused means no further real event is available until something else happens (the next cycle is started, or a protocol switch is resolved). Those two pull results are distinguishable from each other and from a real event.

**Incomplete-event size limit.** The connection is constructed with an incomplete-event size limit. The default is 16 kibibytes, used when `Connection` is called with only the role. A non-default limit is the second positional argument after the role; that two-argument call does not fall back to the default. The limit is judged against an unfinished request or response line plus headers, not against a complete framed body, and not against a header value alone. Concrete quantity: a `GET / HTTP/1.0` request with a `Big` header of 4000 `a` characters succeeds at limit 5000 and fails at 4000 as a remote protocol error suggesting 431; a 10000-byte complete framed body succeeds at 5000; pipelined leftovers fail only when that next message is actually parsed; an unfinished response line plus headers past the limit is the same remote 431.

**Reason phrases.** A caller who wants a reason phrase supplies one. The product does not look one up. An encoded status line without a supplied reason carries an empty reason.

**Chunk extensions.** Extensions on a chunk size line are parsed and discarded. They do not appear on the pulled data event.

## `Connection`

Callable type on the package root. After `import `httpwire``, the name is `httpwire`.`Connection`. It is also importable as `from `httpwire` import `Connection``.

It tracks one HTTP/1.1 connection. It does not open sockets or read from the network.

### Signature

```
`Connection`(role)
`Connection`(role, limit)
```

- `role` — the package-root role value `CLIENT` or `SERVER`, first positional argument.
- `limit` — an integer incomplete-event size limit, second positional argument.

Both arities are published. There is no setter and no third constructor. A one-argument call uses the default limit of 16 kibibytes. A two-argument call uses that integer as the limit. Binding of the two-argument form does not fall back to the default.

```
`Connection`(`CLIENT`)
`Connection`(`SERVER`)
`Connection`(`CLIENT`, 4000)
`Connection`(`SERVER`, 5000)
```

### Return

A connection object. On a connection constructed with `CLIENT`, `our_role` is `CLIENT` and `their_role` is `SERVER`. On a connection constructed with `SERVER`, the pair is reversed. A fresh connection's `our_state` and `their_state` are the package-root `IDLE`.

`CLIENT` and `SERVER` are distinct: they are not the same object and they do not compare equal. A role that is neither `CLIENT` nor `SERVER` is refused and produces no connection.

### Incomplete-event size limit

The second positional argument is the incomplete-event size limit. The omitted second argument is 16 kibibytes. The limit is judged against an unfinished request or response line plus headers, not against a complete framed body, and not against a header value alone.

That integer is the same quantity a later `next_event` measures:

- A server-role connection fed `GET / HTTP/1.0` plus a `Big` header whose value is 4000 `a` characters, then the header terminator, pulls that `Request` plus `EndOfMessage` when the limit is 5000. The same unfinished header fails the pull when the limit is 4000: `RemoteProtocolError` with suggested status 431, `their_state` `ERROR`, `our_state` not `ERROR`.
- A complete request with `Content-Length` 10000 followed by ten thousand `a` body bytes succeeds at limit 5000, because the oversized part is a complete framed body.
- Two pipelined GET requests plus leftover bytes against a smaller limit: the first requests pull, leftovers stay `PAUSED` until `start_next_cycle`, and the 431 happens only when that next message is actually parsed.
- An unfinished response line plus headers past the limit is the same remote 431.

## `Connection.client_is_waiting_for_100_continue`

Attribute on a `Connection` instance. It is whether the client of this HTTP conversation is still waiting for 100-continue.

### Shape

`client_is_waiting_for_100_continue` is present on every `Connection`. The value is the exact type `bool` — true or false, not `None` and not a non-bool stand-in.

The member is a bool on both roles. A `CLIENT` connection and a `SERVER` connection that have processed the same waiting request both report true. A connection that has not processed such a request reports false.

### When it is true

The value is true after a `CLIENT` `send` of a `Request`, or a `SERVER` `next_event` of that same request, when all of the following hold:

- The request HTTP version is `1.1`.
- The request includes an `Expect` header whose value is `100-continue`. Matching ignores letter case: `100-Continue` and mixed letter case of that same value also match.
- The request has a non-empty body: a positive `Content-Length` such as `Content-Length` `100`, or `Transfer-Encoding` `chunked` with no `Content-Length`.

That includes `GET` and methods other than `GET` (for example a `POST` with `Transfer-Encoding` `chunked`). The value is true after the request is sent or pulled and before any of the clears below.

Concrete case: a `CLIENT` `send` of `GET` `/` with `Host` `example.com`, `Content-Length` `100`, and `Expect` `100-continue`, fed to a `SERVER` connection and pulled as a `Request`, leaves this member true on both connections.

A request with the same framing and no `Expect` header leaves this member false on both connections.

### When it is false

An `Expect` `100-continue` header on an HTTP/`1.0` request does not set this member. Concrete case: a complete `GET / HTTP/1.0` request with `Host` `example.com`, `Content-Length` `100`, and `Expect` `100-continue`, fed to a `SERVER` connection and pulled as a `Request`, leaves this member false.

The value becomes false on both roles after any of:

- Any `InformationalResponse`. Status 100, status 102, and any other informational status each clear it. After a `SERVER` `send` of that event and a `CLIENT` pull of it, both connections report false.
- Any final `Response`. Status 200, status 404, and any other final status each clear it. After a `SERVER` `send` of that event and a `CLIENT` pull of it, both connections report false.
- A client-role `send` of `Data` (payload `12345`, or any other non-empty payload). The `CLIENT` connection reports false immediately after that send. The `SERVER` connection reports false after those bytes are given to `receive_data` and pulled as `Data`.
- On a `chunked` `Expect` request that has not yet sent `Data`, a client-role `send` of `EndOfMessage`. The `CLIENT` connection reports false immediately after that send. The `SERVER` connection reports false after those bytes are given to `receive_data` and pulled as `EndOfMessage`.

`they_are_waiting_for_100_continue` is a separate member on the same connection. It is not a substitute for this one.

## `Connection.next_event`

Method on a `Connection` instance. Parses one event from bytes previously given to `receive_data`, reports that more bytes are needed, or reports that no further real event is available until the next cycle is started or a protocol switch is resolved. It does not read a socket.

### Signature

```
`next_event`()
```

No arguments.

### Return

One of:

- The package-root value `NEED_DATA`, when nothing has been stored yet or the stored bytes are not yet a complete event.
- The package-root value `PAUSED`, when no further real event is available until the next cycle is started or a protocol switch is resolved.
- One HTTP event parsed from the stored bytes: `Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, or `ConnectionClosed`.

A fresh `CLIENT` connection and a fresh `SERVER` connection both return `NEED_DATA`. Two such pulls on the same fresh connection return equal values, and a fresh client pull equals a fresh server pull. The call does not fail on a fresh connection.

Each successful call that is not `NEED_DATA` and not `PAUSED` yields exactly one event. Bytes for later events stay stored. Feeding an informational status-100 line plus a final status-200 line in one `receive_data`, then calling `next_event` twice, yields the `InformationalResponse` first and the `Response` second.

When the stored bytes are only a fragment of an event, the call returns `NEED_DATA` and keeps those bytes. A further `receive_data` of the rest, then another `next_event`, completes the same event. The second fragment alone, on a different connection, is not a complete event.

After the last `Content-Length` body bytes have been pulled as a `Data` event, a further `next_event` with no additional `receive_data` yields `EndOfMessage`.

After a client has sent a request, feeding an HTTP/1.0 200 status line with no framing headers, then body bytes `12345` then `67890`, then an empty `receive_data`, successive pulls yield a `Response` whose `http_version` is `1.0`, then `Data` `12345`, then `Data` `67890`, then `EndOfMessage`, then `ConnectionClosed`. That empty chunk ends a close-delimited body. It is not a `RemoteProtocolError`. After that sequence the client side is `MUST_CLOSE`.

An empty `receive_data` while a `Content-Length` body still has bytes outstanding, or while a `chunked` body is still unfinished, is `RemoteProtocolError` from this call, not `EndOfMessage` and not `ConnectionClosed`.

Feeding an empty chunk on a fresh `IDLE` connection, then pulling, yields a `ConnectionClosed` event. On a server-role connection the pair is client `CLOSED` and server `MUST_CLOSE`. On a client-role connection the pair is client `MUST_CLOSE` and server `CLOSED`. A pull before that empty feed is `NEED_DATA`, not `ConnectionClosed`. Once a `ConnectionClosed` event has been pulled, further pulls also yield a `ConnectionClosed` event: a second or third pull is not `NEED_DATA` and not a `RemoteProtocolError`. After a further empty `receive_data`, later pulls still yield `ConnectionClosed`.

After both sides are `DONE`, an empty `receive_data` pulls as `ConnectionClosed` and the receiver that was `DONE` becomes `MUST_CLOSE`.

Two pipelined `GET` requests for `/1` and `/2` with five-byte bodies, then an empty feed: after the second `EndOfMessage` the next pull is `ConnectionClosed`, with client `CLOSED` and server `SEND_RESPONSE`. Without that empty feed the same pull is `NEED_DATA`, not `ConnectionClosed`.

`NEED_DATA` is not an event instance. `PAUSED` is not `NEED_DATA` and is not an event instance. An observer can tell `NEED_DATA` and `PAUSED` apart from each other and from `Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, and `ConnectionClosed`.

After a pipelined leftover, further `next_event` calls stay `PAUSED` until `start_next_cycle`. Feeding more bytes does not parse the next request. Leftovers that exceed the incomplete-event size limit still stay `PAUSED` until the next cycle is started; the 431 is raised only when that next message is actually parsed, not while paused. Concrete case: three `GET` requests for `/1`, `/2`, and `/3` (the first two with `Content-Length` 5 and bodies `12345` and `67890`) fed in one block to a `SERVER` connection. After the `/1` `Request`, the matching `Data`, and `EndOfMessage`, the next pull is `PAUSED`, not `NEED_DATA` and not a `Request`. After a status-200 `Response` plus `EndOfMessage`, and before `start_next_cycle`, a further pull is still `PAUSED`. A further `receive_data` while paused still yields `PAUSED`, not a `Request` for `/2`. After the server sends its response and `EndOfMessage` and calls `start_next_cycle`, pulls yield the leftover `/2` exchange.

After the last pipelined request with no leftover, the pull is `NEED_DATA`, not `PAUSED` and not a `Request`. Concrete case: after `/3` and its `EndOfMessage`, with no further stored bytes, the pull is `NEED_DATA`. If more bytes then arrive, a further pull is `PAUSED` again.

An incomplete current request is still `NEED_DATA`. Feeding only `GET /partial HTTP/1.1\r\n` yields `NEED_DATA`; feeding the rest of that header block then yields that `Request`.

After a finished `CONNECT` or `Upgrade:` proposal — the proposing `Request`'s `Data` (if any) and `EndOfMessage` — the client side is `MIGHT_SWITCH_PROTOCOL`. A server-role pull is then `PAUSED`. That pause is not `NEED_DATA` and is not a `Request`. It happens even when no leftover request bytes are stored. Concrete cases: `CONNECT` `example.com:443` with `Content-Length` `1` and body `1`; the same `CONNECT` with no `Content-Length` and an empty body; `Upgrade:` `a, b` on `GET` `/` with `Content-Length` `1` and body `1`. Before that `EndOfMessage`, an incomplete proposal body is still `NEED_DATA`, not `PAUSED`.

`start_next_cycle` from that pair (client `MIGHT_SWITCH_PROTOCOL`, server `SEND_RESPONSE`) is `LocalProtocolError` and does not enter `ERROR`. Neither side becomes `IDLE`. Denial plus `start_next_cycle` is what unlocks leftover HTTP: feeding `GET / HTTP/1.0` with no headers while paused, then a non-accepting final `Response` plus `EndOfMessage`, still yields `PAUSED` until `start_next_cycle`; after that next cycle the leftover pulls as that `GET` `/` `Request` whose `http_version` is `1.0`, then `EndOfMessage`. A `start_next_cycle` without denial does not parse that leftover as a `Request`.

After acceptance, both sides are `SWITCHED_PROTOCOL`. Further pulls stay `PAUSED`. Bytes fed after the accepting response are not parsed as HTTP. Concrete case: feeding `123` then `456` leaves `trailing_data` as `123456` with the receive side still open; pulls remain `PAUSED`, not a `Request`. Acceptance is a final 2xx `Response` to a finished `CONNECT` proposal (status 200, or any other 2xx), or an `InformationalResponse` whose status is 101 to a finished `Upgrade:` proposal.

An empty `receive_data` while paused for a switch proposal stays `PAUSED`: it is not a `ConnectionClosed` event. That empty chunk sets the `trailing_data` receive-closed flag. After a denial, that empty feed is then pulled as `ConnectionClosed`. After acceptance, the pull stays `PAUSED` and is still not `ConnectionClosed`.

`NEED_DATA`, pipelining `PAUSED`, and switch `PAUSED` unlock differently. `NEED_DATA` becomes a real event after more bytes of the current HTTP message (for example a status-line prefix `HTTP/1.1 20` then the rest of a status-200 response). Pipelining `PAUSED` becomes a real event after `start_next_cycle`, with no switch denial required. Switch `PAUSED` does not unlock by feeding more bytes or by `start_next_cycle` alone: after acceptance it stays `PAUSED` forever; after a proposal that has not been denied, `start_next_cycle` is the local refusal above and the leftover is still not a `Request`.

The events one role encodes with `send` are the events the other role pulls. A server that is fed a client-encoded `GET` for `/` with `Host` `example.com` and `Content-Length` `10`, then pulled, yields a `Request` whose `method` is `GET`, `target` is `/`, and ordinary headers include `host` `example.com` and `content-length` `10`.

### Side effects

A successful event return updates connection state for that peer event. After that GET is pulled, both connections show client-side `SEND_BODY` and server-side `SEND_RESPONSE`. Returning `NEED_DATA` does not advance states and does not record a peer HTTP version. Returning `PAUSED` does not parse the next stored request, and does not parse bytes that arrived after a protocol-switch acceptance as HTTP. The method does not open, read, or write a socket.

### Raised failures

Peer bytes that are not a legal message are refused as `RemoteProtocolError`, not as `LocalProtocolError`. `receive_data` of those bytes succeeds; the refusal is raised from `next_event`. Concrete refusals:

- A folded continuation as the first header
- A header name with trailing spaces or a trailing tab before the colon
- A header line with no name before the colon
- Garbage after the request line or after the response line
- A NUL inside a header value
- A request target containing a NUL, a space, byte 127, or byte 238
- Bytes that cannot be a request or response even before a line ending arrives: a single NUL, a single space, or the opening bytes of a TLS Client Hello (server-role) or TLS Server Hello (client-role after a request has been sent)
- Only a blank line, on a server-role connection or on a client-role connection that has already sent a request
- An empty `receive_data` while a `Content-Length` body still has bytes outstanding
- An empty `receive_data` while a `chunked` body is still unfinished
- An empty `receive_data` in the middle of a request line (server fed `GET /` then an empty chunk): remote suggested status 400, not `ConnectionClosed`
- The public `gibberish` line plus a blank line: remote suggested status 400, not `ConnectionClosed`. `their_state` becomes `ERROR` and `our_state` does not

A pull that would have to keep an unfinished request or response line plus headers past the connection's incomplete-event size limit is `RemoteProtocolError` with suggested status 431, not `NEED_DATA` and not a `Request` or `Response`. `their_state` becomes `ERROR` and `our_state` does not. The limit is judged against that unfinished line plus headers, not against a header value alone. The default limit is 16 kibibytes on a one-argument `Connection`(role) construction. Concrete cases: a `GET / HTTP/1.0` plus a `Big` header of 4000 `a` characters succeeds at limit 5000 and fails at 4000 with 431; an unfinished response line plus headers past the limit is the same remote 431; feeding an endless header in 1024-byte pieces on a default-limit connection eventually fails with 431.

Pipelined leftovers over the limit stay `PAUSED` until `start_next_cycle`. The 431 happens only when that next message is actually parsed.

After any remote pull error, further `next_event` calls are `RemoteProtocolError`. Feeding a well-formed later request does not recover receive. `their_state` stays `ERROR` and `our_state` is not `ERROR`.

An empty `receive_data` that ends an HTTP/1.0 close-delimited body is not a refusal. That walk is `EndOfMessage` then `ConnectionClosed`, as under Return.

A client that has finished its request and is waiting with `their_state` `SEND_RESPONSE`, then pulls an empty `receive_data`, sees `RemoteProtocolError` and not a `ConnectionClosed` event. `their_state` becomes `ERROR` and `our_state` does not. A further pull stays the same remote refusal.

Feeding a complete new `GET` while the peer is `MUST_CLOSE` (after this side sent `ConnectionClosed`) fails this pull as `RemoteProtocolError`, not as `ConnectionClosed` and not as a `Request`. `their_state` becomes `ERROR` and `our_state` does not. A further pull stays the same remote refusal. That remote error is not the runtime error raised when a nonempty chunk is stored after an empty chunk has already been stored; that store failure is on `receive_data`, not on this call.

### Accepted receive dialect

A pull accepts a lone line feed, or a mix of carriage-return/line-feed and lone line feed, as header-block line endings. A status line that omits the reason phrase pulls with an empty reason. A header whose value is empty, or only tabs and spaces, pulls as an empty value. A single-character header value is accepted. Obsolete line folding joins continuation lines: leading whitespace on each continuation collapses to a single space. A header that is the last header may also be folded.

A peer HTTP/1.0 request `GET / HTTP/1.0` with no headers pulls as a `Request` whose `http_version` is `1.0`, then `EndOfMessage`.

## `Connection.our_role`

Attribute on a `Connection` instance. It is the role this connection is playing.

### Shape

`our_role` is the package-root role value passed to `Connection` at construction: `CLIENT` or `SERVER`. It is that same object, not a parallel spelling.

- On a connection constructed with `CLIENT`, `our_role` is `CLIENT`.
- On a connection constructed with `SERVER`, `our_role` is `SERVER`.

`CLIENT` and `SERVER` are distinct: they are not the same object and they do not compare equal. `their_role` on the same connection is the complementary package-root role.

## `Connection.receive_data`

Method on a `Connection` instance. Stores a received byte chunk for a later `next_event`. It does not parse, does not read a socket, and is not the same operation as `send`.

### Signature

```
`receive_data`(data)
```

- `data` — one byte chunk just received from the peer.

The call returns no event. A successful store raises nothing.

### Store-only

The chunk is retained. States do not advance: after a complete request is stored and before any `next_event`, `our_state` and `their_state` remain `IDLE`. `their_http_version` stays absent (missing, `None`, or empty). Parsing happens only on a later `next_event`.

An empty chunk means the receive side closed. The first empty chunk succeeds. Further empty chunks after that first empty chunk also succeed.

### Raised failures

A nonempty chunk after an empty chunk has already been stored is a runtime error. That failure is neither `LocalProtocolError` nor `RemoteProtocolError`. An observer can tell the three kinds apart. No additional protocol-error type is required for this case.

Illegal peer bytes are not refused here. `receive_data` of those bytes succeeds; `next_event` is what raises `RemoteProtocolError`.

## `Connection.send`

Method on a `Connection` instance. Encodes one event into bytes the integrator must transmit. It does not write a socket and is not the same operation as `receive_data`.

### Signature

```
`send`(event)
```

- `event` — one HTTP event: `Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, or `ConnectionClosed`. A `ConnectionClosed` event is constructed with no fields.

### Return

A successful call that produced wire bytes returns a byte buffer (`bytes`, or a `bytearray` / `memoryview` of those bytes).

A successful `send` of a `ConnectionClosed` event produces no bytes: the return is `None` or a zero-length buffer. That is a successful encode, not a failure. An exception is never classified as no bytes.

When `Content-Length` is already satisfied and an `EndOfMessage` is sent, the return is `None` or a zero-length buffer. That is a successful encode with no extra bytes, not a failure.

A missing buffer is not a successful encode of a request, informational-response, response, or data event that has bytes to write. That missing-buffer rule does not apply to a successful `ConnectionClosed` send.

### Encoded shape

The product encodes only HTTP/1.1. That is a refusal of an event whose `http_version` is `1.0` at `send`, not a rewrite of `1.0` into `1.1` on the wire. A client-role `send` of a `GET` request for `/` with `Host` `example.com` and `Content-Length` `10` yields a complete request: a request line naming `GET`, `/`, and version `1.1`, then the headers, then a blank line.

When encoding a request, the `Host` header is written before every other header, even if it was not first in the caller’s list. The original name casing from construction is what is written.

An informational-response or response status line carries an empty reason unless the caller supplied one. The product does not invent a phrase such as `OK`.

A `Data` event under `Content-Length` framing encodes as exactly that payload, with no extra framing.

### Side effects

`send` never opens, reads, or writes a socket. The integrator receives the returned buffer (or no extra bytes) and transmits it.

After a client-role `send` of that GET, the client-side state is `SEND_BODY` and the server-side state is `SEND_RESPONSE`. After a server-role `send` of the matching status-200 response with `Content-Length` `11`, both sides are `SEND_BODY`. After both sides have sent their matching `EndOfMessage` events on an HTTP/`1.1` exchange with no Connection close token, both sides are `DONE`.

A server in `SEND_RESPONSE` that sends an `InformationalResponse` stays in `SEND_RESPONSE` when that status is an ordinary 1xx: status 100, status 102, or any other informational status that is not 101. Two such informational responses in a row still leave that server in `SEND_RESPONSE`. The following final `Response` moves it to `SEND_BODY`.

Status 101 is the exception: it is `Upgrade:` acceptance. After a server-role `send` of an `InformationalResponse` whose status is 101 on a finished `Upgrade:` proposal (including a request that also proposed `CONNECT`), and after the client pulls that event, both sides are `SWITCHED_PROTOCOL`, not `SEND_RESPONSE`.

A final 2xx `Response` to a finished `CONNECT` proposal is the `CONNECT`-accept exception: status 200, and any other 2xx, each put both sides in `SWITCHED_PROTOCOL` after that send and the client pull. That acceptance does not include an `EndOfMessage`; the connection has left HTTP.

A non-2xx `CONNECT` `Response` (status 404, or any other final non-2xx) and a final non-101 `Upgrade:` `Response` (status 200, status 204, or any other final non-101) remain ordinary denials. After that denial `Response` the pair is client `DONE` and server `SEND_BODY`; after the matching `EndOfMessage` both sides are `DONE`, and `start_next_cycle` is then allowed.

A server in `IDLE` may send a `Response` with no request present. That send encodes. Status 408 is the public sample; a final status that is not 408 also encodes. After that send the server is `SEND_BODY`.

When keep-alive is disabled, a side that would have entered `DONE` enters `MUST_CLOSE` instead, and `start_next_cycle` is then refused. Keep-alive is disabled when a Connection close token is recognized case-insensitively in a comma-separated Connection value (for example `a, b, cLOse, foo`), when either side spoke HTTP/`1.0`, or when the server sets close. An HTTP/`1.0` `keep-alive` token does not enable reuse. A server status-200 or status-204 `Response` sent with no Connection header still encodes a close token when keep-alive is already disabled.

Either role in `IDLE` may send `ConnectionClosed`. A fresh client-role send puts the client side `CLOSED` and the server side `MUST_CLOSE`. A fresh server-role send puts the server side `CLOSED` and the client side `MUST_CLOSE`. The peer may then itself send `ConnectionClosed`; both sides end `CLOSED`.

After a full request and a full response, either side may send `ConnectionClosed`. The other side becomes `MUST_CLOSE` if it was `DONE`. Sending `ConnectionClosed` when that side is already `CLOSED` succeeds and does not fail.

A server in `MUST_CLOSE` — including after an HTTP/`1.0` exchange, and after the second status-200 of two pipelined `GET` requests for `/1` and `/2` with five-byte bodies — sends `ConnectionClosed` and enters `CLOSED`.

A client half-close after a finished `GET` `/foo` with `Host` `a`, or after a finished `Content-Length` body plus `EndOfMessage`, leaves the client side `CLOSED` and the server side `SEND_RESPONSE`, so the server can still send the response.

A client-role `send` of a request does not record `their_http_version` on that client.

After a remote receive error, `send` still works. A server that pulled `gibberish` plus a blank line can still encode a status-400 `Response` with empty headers: the status line is 400, the bytes carry a Connection close token, `our_state` is not `ERROR`, and `their_state` stays `ERROR`. A mid-request-line empty feed is the same send-still-works walk: that server can still encode a status-400 `Response` with empty headers, the status line is 400, `our_state` is not `ERROR`, and `their_state` stays `ERROR`.

### Raised failures

A client-role `send` of a `Response` is `LocalProtocolError`, not `RemoteProtocolError`. A server-role `send` of a `Request` is the same local refusal. A client-role `send` of a second `Request` before `start_next_cycle` is the same local refusal. Those calls yield no bytes.

A client-role `send` of a `Request` whose `http_version` is `1.0` is `LocalProtocolError`, not `RemoteProtocolError`. Suggested status is 400. That includes `GET` and `HEAD`. The call yields no bytes. `our_state` becomes `ERROR` and `their_state` does not. A later `1.1` request that would have succeeded on a fresh connection also fails as the same local refusal; `our_state` stays `ERROR`.

A server-role `send` of a `Response` whose `http_version` is `1.0` is the same unrecoverable local error, both from `IDLE` (status 408) and after a pulled request (status 200). Suggested status is 400. The call yields no bytes. `our_state` becomes `ERROR` and `their_state` does not. A later `1.1` response that would have succeeded on a fresh connection also fails.

A server in `SEND_RESPONSE` cannot send `ConnectionClosed`. That send is `LocalProtocolError`, not `RemoteProtocolError`. The call yields no bytes. `our_state` becomes `ERROR` and `their_state` does not. A further send still fails as the same local refusal. That includes a server that has pulled a complete request (empty-body or a finished `Content-Length` body) and a server whose client has already half-closed: the pair is then client `CLOSED` and server `SEND_RESPONSE`, and that server still cannot send `ConnectionClosed`.

A client or server in `SEND_BODY` in the middle of a `Content-Length` body cannot send `ConnectionClosed`. That send is the same local protocol error. The call yields no bytes. `our_state` becomes `ERROR` and `their_state` does not. After that body's `EndOfMessage` has been sent, a later `ConnectionClosed` is allowed.

Once both sides are `SWITCHED_PROTOCOL`, a further HTTP event is `LocalProtocolError`, not `RemoteProtocolError`. That includes a server-role `Data`, a client-role `Request`, and a server-role `EndOfMessage`, after a `CONNECT` 2xx or an `Upgrade:` 101. Those calls yield no bytes. `our_state` becomes `ERROR` and `their_state` does not. A further send still fails as the same local refusal. `SWITCHED_PROTOCOL` is permanent. This send refusal is not the recoverable `start_next_cycle` refusal.

## `Connection.send_failed`

Method on a `Connection` instance. Tells the connection that the integrator did not actually transmit the bytes a previous `send` produced. It does not write a socket and is not the same operation as `send`.

The method is a distinct bound attribute whose name is `send_failed`. Implementing only `send`, `receive_data`, `next_event`, and `start_next_cycle` does not provide this operation.

### Signature

```
`send_failed`()
```

No arguments.

### Return

The call returns without raising.

### Side effects

The call does not open, read, or write a socket. It produces no wire bytes.

`our_state` becomes `ERROR`. `their_state` is not `ERROR`.

`their_state` is otherwise unchanged, except when it was already `DONE`: then it becomes `MUST_CLOSE`.

Calling `send_failed` twice in a row has the same result: `our_state` stays `ERROR`, and `their_state` is the same as after the first call.

Concrete cases:

- After a client-role `send` of a `GET` for `/` with `Host` `example.com`, `their_state` is `SEND_RESPONSE`. `send_failed` then leaves `their_state` as `SEND_RESPONSE` and sets `our_state` to `ERROR`.
- After a server-role connection has pulled that request plus `EndOfMessage` and `send` of a status-200 `Response` with empty headers, `their_state` is `DONE`. `send_failed` then sets `their_state` to `MUST_CLOSE` and `our_state` to `ERROR`.

After this call, a following `send` is `LocalProtocolError`, not `RemoteProtocolError`. Suggested status is 400. `our_state` stays `ERROR` and `their_state` is still not `ERROR`. Concrete case: a client-role or server-role `send` of `EndOfMessage` after `send_failed` is that local refusal. The same `EndOfMessage` `send` succeeds on a connection that has not called `send_failed`.

`start_next_cycle` after this call does not return `our_state` to `IDLE`, `DONE`, or any other state. `our_state` stays `ERROR`. There is no operation that leaves `ERROR`.

## `Connection.send_with_data_passthrough`

Method on a `Connection` instance. Encodes one event as a sequence of pieces, keeping a caller-supplied body placeholder intact. It does not write a socket. It is not `send`: `send` returns one concatenated byte buffer.

The method is a distinct bound attribute whose name is `send_with_data_passthrough`. Implementing only `send` does not provide this operation.

### Signature

```
`send_with_data_passthrough`(event)
```

- `event` — one HTTP event. The placeholder cases pass a `Data` event whose `data` is a non-byte object with a length, not a byte string.

### Return

A successful call returns a sequence of pieces. The return is not a concatenated byte string, not `None`, and not a raised exception. A raised exception is a failure, not an empty piece list.

When the `Data` payload is a placeholder object rather than a byte string, that same object appears in the sequence by identity — not a copy and not concatenated into bytes.

Concrete cases, after a server-role connection has received `GET` `/` and sent a status-200 response:

- `Content-Length` `10` and a placeholder of length 10: the sequence is only that same object.
- `Transfer-Encoding` `chunked`: the sequence still contains that same object among framing pieces. The other pieces are byte buffers. Substituting ten `x` bytes for the object and joining the sequence produces a well-formed chunk whose payload is those ten bytes.
- HTTP/`1.0` close-delimited framing (a 200 with no framing headers after an HTTP/`1.0` `GET`): the sequence is only that same object.

A length that is not 10 behaves the same way: a `Content-Length` of N and a placeholder of length N yields a sequence that is only that object; chunked framing still keeps that object among framing pieces.

### Side effects

The call does not open, read, or write a socket. The integrator receives the piece sequence and transmits each piece.

The connection counts the placeholder’s length as body bytes sent. After a `Content-Length` 10 passthrough of a length-10 placeholder, a following `send` of `EndOfMessage` succeeds and produces no extra bytes (`None` or a zero-length buffer).

A shorter placeholder still returns a sequence that contains that object. A following `send` of `EndOfMessage` is then refused as `LocalProtocolError`, not as `RemoteProtocolError`. Concrete cases: `Content-Length` `10` and a placeholder of length 7, then `EndOfMessage`; or `Content-Length` N+4 and a placeholder of length N, then `EndOfMessage`.

## `Connection.start_next_cycle`

Method on a `Connection` instance. Resets a reusable connection so another request/response can run on it. It does not read or write a socket.

### Signature

```
`start_next_cycle`()
```

No arguments.

### Return

When both sides are `DONE`, the call returns without raising.

### Side effects

A successful call sets both `our_state` and `their_state` to `IDLE`. A second request/response can then run on the same connection. Concrete case: client `GET` `/` with `Host` `a` plus `EndOfMessage`, server status-200 plus `EndOfMessage`, both sides `DONE`, `start_next_cycle` on each connection, then client `DELETE` `/foo` with `Host` `a` plus `EndOfMessage`, server status-404 plus `EndOfMessage`. After that second cycle both sides are `DONE` again.

The peer HTTP version recorded on `their_http_version` stays present. After a server-role pull of an HTTP/`1.1` request records `1.1`, a later successful `start_next_cycle` still reports that same `1.1`.

Keep-alive is enabled when, and only when, both sides speak HTTP/`1.1` and neither side has set a Connection `close` token. The token is recognized case-insensitively inside a comma-separated Connection value. When keep-alive stays enabled, both sides enter `DONE` and this call succeeds. A Connection token that only contains `close` as a substring of another token (for example `enclosed`) does not disable keep-alive.

### Raised failures

When either side is not `DONE` and neither side is already `ERROR`, the call is `LocalProtocolError`, not `RemoteProtocolError`. It yields no successful reset: both sides are not `IDLE`. Neither side is `ERROR`. When the missing `DONE` is an unfinished HTTP cycle, the connection remains usable: a later call from both `DONE` still succeeds.

When both sides are `SWITCHED_PROTOCOL`, the call is that same local refusal. It yields no successful reset. Neither side is `ERROR`. Both sides stay `SWITCHED_PROTOCOL`, not `DONE` and not `IDLE`. There is no later call from both `DONE`: `SWITCHED_PROTOCOL` is permanent.

When the client side is `MIGHT_SWITCH_PROTOCOL` and the server side is `SEND_RESPONSE`, the call is that same local refusal. Neither side is `ERROR`. The client stays `MIGHT_SWITCH_PROTOCOL` and the server stays `SEND_RESPONSE`, not `IDLE`. Completing a denial to both `DONE` then allows a later successful call. Acceptance into `SWITCHED_PROTOCOL` does not.

When a side is already `ERROR`, the call does not return that side to `IDLE`, `DONE`, or any other state. That side stays `ERROR`. There is no operation that leaves `ERROR`. Concrete cases: after a remote pull of `gibberish` plus a blank line, `start_next_cycle` leaves `their_state` as `ERROR`, not `IDLE` or `DONE`; after an HTTP/`1.0` send error, it leaves `our_state` as `ERROR`; after `send_failed`, `our_state` does not return to `IDLE`.

Concrete refusals that leave the connection usable (neither side was already `ERROR`):

- A client in `SEND_BODY` (request sent, body not finished). After the refusal, `our_state` is still `SEND_BODY`. Completing that cycle and then calling `start_next_cycle` succeeds and both sides become `IDLE`.
- A client whose own side is `DONE` while the peer is still `SEND_RESPONSE` (response not yet pulled). Completing the response and then calling `start_next_cycle` succeeds.
- A server in `SEND_RESPONSE` (request pulled, response not yet sent). Completing an ordinary HTTP response and then calling `start_next_cycle` succeeds. Completing a switch-accept response does not: both sides are then `SWITCHED_PROTOCOL`, as above.
- A call before the first cycle has reached both `DONE`. After that refusal, finishing the cycle and calling again succeeds.

When keep-alive is disabled, a side that would have entered `DONE` enters `MUST_CLOSE` instead, and this call is the same local refusal. Those sides were not already `ERROR`, so neither side is `ERROR`. Those sides stay `MUST_CLOSE`. Keep-alive is disabled when:

- A Connection `close` token is present (case-insensitive, including inside a comma list such as `a, b, cLOse, foo`, or a server-set `close`).
- Either side spoke HTTP/`1.0`. An HTTP/`1.0` `keep-alive` token does not enable reuse.
- A server in `IDLE` sent a response with `Connection: close` (for example status 408) and then `EndOfMessage`.

An HTTP/`1.0` exchange that has already reached both `MUST_CLOSE` is refused. After that refusal both sides stay `MUST_CLOSE`.

## `Connection.states`

Attribute on a `Connection` instance. It is the queryable pair of states for both sides of the conversation.

### Shape

`states` is present on every `Connection`. `our_state` and `their_state` are also queryable; they are not a substitute for this attribute.

The value is either:

- A mapping keyed by role: `CLIENT` and `SERVER` (or by this connection's `our_role` and `their_role`). The value under `CLIENT` is the client-side state; the value under `SERVER` is the server-side state.
- A two-item sequence that resolves to client-side then server-side. On a `CLIENT` connection that sequence is our state then their state. On a `SERVER` connection it is either our-then-their or their-then-our, matching the two side values.

### Values

Each side's value is one of the nine package-root states: `IDLE`, `SEND_RESPONSE`, `SEND_BODY`, `DONE`, `MUST_CLOSE`, `CLOSED`, `MIGHT_SWITCH_PROTOCOL`, `SWITCHED_PROTOCOL`, or `ERROR`. Those nine names are importable from `httpwire`. They are nine distinct objects; no two compare equal.

A fresh `CLIENT` connection and a fresh `SERVER` connection both start with client-side `IDLE` and server-side `IDLE`. The pair, `our_state`, and `their_state` agree.

After a client-role `send` of a `GET` for `/` with `Host` `example.com` and `Content-Length` `10`, the pair is client-side `SEND_BODY` and server-side `SEND_RESPONSE`. After that request is pulled on a server-role connection, that server's pair is the same. After the server then sends a status-200 response with `Content-Length` `11`, both sides are `SEND_BODY`. After both sides have sent their matching `EndOfMessage` events, both sides are `DONE`.

`receive_data` alone does not advance the pair: after a complete request is stored and before any `next_event`, both sides remain `IDLE`.

## `Connection.their_http_version`

Attribute on a `Connection` instance. It is this connection’s record of the peer’s HTTP version.

### Shape

The recorded value, when present, is the version `1.1` or `1.0` as a byte string or as native text.

Absence is a classified empty record: the attribute may be missing, or present as `None`, or present as empty bytes or empty text. Absence is not rewritten as `1.1`.

### When it is absent

After a client-role `send` of a request, `their_http_version` on that client is absent. After `receive_data` of those bytes on a server-role connection and before any `next_event`, the server’s record is also absent.

### When it is recorded

A successful `next_event` of a peer HTTP/1.1 request records `1.1`. A successful `next_event` of a peer HTTP/1.0 request such as `GET / HTTP/1.0` records `1.0`.

The record is not overwritten by a later `send` on this cycle. A server that has pulled an HTTP/1.0 request and then sends an HTTP/1.1 response still reports `1.0`.

## `Connection.their_role`

Attribute on a `Connection` instance. It is the peer’s HTTP role — the side this connection is not playing.

### Shape

`their_role` is the complementary package-root role value.

- On a connection constructed with `CLIENT`, `their_role` is `SERVER`.
- On a connection constructed with `SERVER`, `their_role` is `CLIENT`.

`CLIENT` and `SERVER` are distinct: they are not the same object and they do not compare equal. `our_role` on the same connection is the role passed to `Connection`.

## `Connection.they_are_waiting_for_100_continue`

Attribute on a `Connection` instance. It is whether the peer is still waiting for 100-continue.

### Shape

`they_are_waiting_for_100_continue` is present on every `Connection`. The value is the exact type `bool` — true or false, not `None` and not a non-bool stand-in.

This member is true only on a `SERVER` connection, and only while that peer is waiting. On a `CLIENT` connection the value is false even when `client_is_waiting_for_100_continue` on that same connection is true.

### When it is true

The value is true on a `SERVER` connection after that connection’s `next_event` of a `Request` (or, symmetrically, after the matching `CLIENT` `send` of that request has been fed and pulled) when all of the following hold:

- The request HTTP version is `1.1`.
- The request includes an `Expect` header whose value is `100-continue`. Matching ignores letter case: `100-Continue` and mixed letter case of that same value also match.
- The request has a non-empty body: a positive `Content-Length` such as `Content-Length` `100`, or `Transfer-Encoding` `chunked` with no `Content-Length`.

That includes `GET` and methods other than `GET` (for example a `POST` with `Transfer-Encoding` `chunked`). The value is true after the request is sent or pulled and before any of the clears below.

Concrete case: a `CLIENT` `send` of `GET` `/` with `Host` `example.com`, `Content-Length` `100`, and `Expect` `100-continue`, fed to a `SERVER` connection and pulled as a `Request`, leaves this member true on the `SERVER` connection and false on the `CLIENT` connection. `client_is_waiting_for_100_continue` is true on both.

A request with the same framing and no `Expect` header leaves this member false on both connections.

### When it is false

On a `CLIENT` connection this member is false in every case above, including while the client is waiting.

An `Expect` `100-continue` header on an HTTP/`1.0` request does not set this member on either role. Concrete case: a complete `GET / HTTP/1.0` request with `Host` `example.com`, `Content-Length` `100`, and `Expect` `100-continue`, fed to a `SERVER` connection and pulled as a `Request`, leaves this member false. `client_is_waiting_for_100_continue` is also false.

The value becomes false after any of the same clears that clear `client_is_waiting_for_100_continue`:

- Any `InformationalResponse`. Status 100, status 102, and any other informational status each clear it. After a `SERVER` `send` of that event and a `CLIENT` pull of it, both connections report false.
- Any final `Response`. Status 200, status 404, and any other final status each clear it. After a `SERVER` `send` of that event and a `CLIENT` pull of it, both connections report false.
- A client-role `send` of `Data` (payload `12345`, or any other non-empty payload). The `CLIENT` connection already reports false for this member. The `SERVER` connection reports false after those bytes are given to `receive_data` and pulled as `Data`.
- On a `chunked` `Expect` request that has not yet sent `Data`, a client-role `send` of `EndOfMessage`. The `CLIENT` connection already reports false for this member. The `SERVER` connection reports false after those bytes are given to `receive_data` and pulled as `EndOfMessage`.

`client_is_waiting_for_100_continue` is a separate member on the same connection. It is not a substitute for this one.

## `Connection.trailing_data`

Attribute on a `Connection` instance. It is this connection’s record of bytes that have been fed but not yet parsed, plus whether the receive side has been closed.

### Shape

`trailing_data` is a two-item pair:

- The first item is the leftover bytes: a byte buffer (`bytes`, or a `bytearray` / `memoryview` of those bytes).
- The second item is the receive-closed flag. It is true when an empty chunk has already been given to `receive_data`.

### When leftover bytes are held

After the last pipelined request of a keep-alive cycle with no leftover, `next_event` is `NEED_DATA`. If more bytes then arrive, `next_event` is `PAUSED` and the first item of `trailing_data` holds those leftover bytes. Concrete case: after `/3` is pulled through `EndOfMessage`, a further `receive_data` of `GET /4 HTTP/1.1\r\nHost: a\r\n\r\n` makes the next pull `PAUSED`, and that request byte string is contained in the first item. A further `next_event` stays `PAUSED` and is not a `Request`.

## `httpwire`

The installable distribution and the importable top-level package are both `httpwire`. Callers declare the interface from this package root (`import `httpwire`` or `from `httpwire` import ...`). Importing the package performs no I/O, starts no processes, and opens no sockets.

The importable package is a single top-level directory named `httpwire`.

After `import `httpwire``, the module's `__name__` is a text string. The first segment of that string, obtained by `split` on the period with at most one cut, equals `httpwire`.

These names are importable as ``httpwire`.<name>` and as `from `httpwire` import <name>`:

- `CLIENT`
- `CLOSED`
- `Connection`
- `ConnectionClosed`
- `Data`
- `DONE`
- `EndOfMessage`
- `ERROR`
- `IDLE`
- `InformationalResponse`
- `LocalProtocolError`
- `MIGHT_SWITCH_PROTOCOL`
- `MUST_CLOSE`
- `NEED_DATA`
- `PAUSED`
- `RemoteProtocolError`
- `Request`
- `Response`
- `SEND_BODY`
- `SEND_RESPONSE`
- `SERVER`
- `SWITCHED_PROTOCOL`

`Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, `ConnectionClosed`, and `Connection` are callable. `LocalProtocolError` and `RemoteProtocolError` are classes. `CLIENT` is the client-role value passed to `Connection` as the first positional argument. `SERVER` is the server-role value passed to `Connection` as the first positional argument. `Connection` is called with the role alone, or with the role then an integer incomplete-event size limit as a second positional argument. The omitted second argument is 16 kibibytes. Both arities are published. `NEED_DATA` is the pull result when more bytes must be given to `receive_data`. `PAUSED` is the pull result when no further real event is available until the next cycle is started or a protocol switch is resolved.

The nine states a side can be in are package-root exports, not strings and not values that exist only on a `Connection`: `IDLE`, `SEND_RESPONSE`, `SEND_BODY`, `DONE`, `MUST_CLOSE`, `CLOSED`, `MIGHT_SWITCH_PROTOCOL`, `SWITCHED_PROTOCOL`, and `ERROR`. They are nine distinct objects; no two compare equal. A fresh `CLIENT` connection's `our_state` and `their_state` are the package-root `IDLE`.

Typical import used to construct events, a client-role or server-role connection, the two protocol-error types, the need-data result, the paused result, and the nine states:

```
import `httpwire`
```

```
from `httpwire` import `CLIENT`, `SERVER`, `Connection`, `ConnectionClosed`, `Data`, `EndOfMessage`, `InformationalResponse`, `LocalProtocolError`, `RemoteProtocolError`, `Request`, `Response`, `NEED_DATA`, `PAUSED`, `IDLE`, `SEND_RESPONSE`, `SEND_BODY`, `DONE`, `MUST_CLOSE`, `CLOSED`, `MIGHT_SWITCH_PROTOCOL`, `SWITCHED_PROTOCOL`, `ERROR`
```

A script that only needs a subset may import that subset, for example `from `httpwire` import `Request``. Attribute access on the imported module is equivalent: ``httpwire`.`Request``, ``httpwire`.`InformationalResponse``, ``httpwire`.`Response``, ``httpwire`.`Data``, ``httpwire`.`EndOfMessage``, ``httpwire`.`ConnectionClosed``, ``httpwire`.`Connection``, ``httpwire`.`CLIENT``, ``httpwire`.`SERVER``, ``httpwire`.`NEED_DATA``, ``httpwire`.`PAUSED``, ``httpwire`.`LocalProtocolError``, ``httpwire`.`RemoteProtocolError``, ``httpwire`.`IDLE``, ``httpwire`.`SEND_RESPONSE``, ``httpwire`.`SEND_BODY``, ``httpwire`.`DONE``, ``httpwire`.`MUST_CLOSE``, ``httpwire`.`CLOSED``, ``httpwire`.`MIGHT_SWITCH_PROTOCOL``, ``httpwire`.`SWITCHED_PROTOCOL``, ``httpwire`.`ERROR``.

When `httpwire` is not importable, a program that does `import `httpwire``, takes `Request` from that module, and constructs `Request` with `method` `GET`, `target` `/`, and `headers` `[('Host', 'example.com')]` does not run to completion and does not yield a request event. When the package is importable, that same construction succeeds.

## `httpwire.NEED_DATA`

Package-root pull result. After `import `httpwire``, the name is `httpwire`.`NEED_DATA`. It is also importable as `from `httpwire` import `NEED_DATA``.

### Shape

`NEED_DATA` is the value `Connection`.`next_event` returns when no further real event is available until more bytes are given to `receive_data`.

A fresh `CLIENT` connection and a fresh `SERVER` connection both return this value. Two such pulls on the same fresh connection return equal values, and a fresh client pull equals a fresh server pull. Those results compare equal to the package-root `NEED_DATA`.

`NEED_DATA` is not an event instance. An observer can tell it apart from `Request`, `InformationalResponse`, `Response`, `Data`, and `EndOfMessage`.

When stored bytes are only a fragment of an event, `next_event` returns `NEED_DATA` and keeps those bytes.

## `httpwire.PAUSED`

Package-root pull result. After `import `httpwire``, the name is `httpwire`.`PAUSED`. It is also importable as `from `httpwire` import `PAUSED``.

### Shape

`PAUSED` is the value `Connection`.`next_event` returns when no further real event is available until something else happens — the next cycle is started, or a protocol switch is resolved.

A successful pull that yields `PAUSED` compares equal to the package-root `PAUSED` (identity or equality). `PAUSED` is not `NEED_DATA`. `PAUSED` is not an event instance. An observer can tell it apart from `NEED_DATA` and from `Request`, `InformationalResponse`, `Response`, `Data`, `EndOfMessage`, and `ConnectionClosed`.

### When a pull is `PAUSED`

As a server, after a pipelined leftover, `next_event` returns `PAUSED` and does not parse the next request. Concrete case: three `GET` requests for `/1`, `/2`, and `/3` (the first two with `Content-Length` 5 and bodies `12345` and `67890`) fed in one block to a `SERVER` connection. After the `/1` `Request`, the matching `Data`, and `EndOfMessage`, the next `next_event` is `PAUSED`, not `NEED_DATA` and not a `Request`. After a status-200 `Response` plus `EndOfMessage`, and before `start_next_cycle`, a further `next_event` is still `PAUSED`.

Further `next_event` calls stay `PAUSED` until `start_next_cycle`. A further `receive_data` while paused does not make the next request appear: feeding extra request bytes still yields `PAUSED`, not a `Request` for `/2`. After the server sends its response and `EndOfMessage` and calls `start_next_cycle`, pulls yield the leftover `/2` exchange.

The same pause happens after an empty-body first request when a second request is already stored: after that first `Request` and `EndOfMessage`, the next pull is `PAUSED`, not a `Request`.

If more bytes arrive after `/3` is done (the last pipelined request, no leftover), a pull is `PAUSED` and `trailing_data` holds those leftover bytes. A further `next_event` stays `PAUSED` and is not a `Request`.

### When a pull is not `PAUSED`

After the last pipelined request with no leftover, `next_event` returns `NEED_DATA`, not `PAUSED` and not a `Request`. Concrete case: after `/3` and its `EndOfMessage`, with no further stored bytes, the pull is `NEED_DATA`.

An incomplete current request is still `NEED_DATA`. Concrete contrast: feeding only `GET /partial HTTP/1.1\r\n` yields `NEED_DATA`; feeding the rest of that header block then yields that `Request`.

## `httpwire.SERVER`

Package-root server-role value. After `import `httpwire``, the name is `httpwire`.`SERVER`. It is also importable as `from `httpwire` import `SERVER``.

### Shape

`SERVER` is the server-role value passed to `Connection`. It is the complement of `CLIENT`. It is the first positional argument of that constructor.

```
`Connection`(`SERVER`)
`Connection`(`SERVER`, 5000)
```

The one-argument call produces a server-role connection: `our_role` is `SERVER` and `their_role` is `CLIENT`. A connection constructed with `CLIENT` has the reverse pair. Both arities are published. The two-argument form passes an integer incomplete-event size limit as the second positional argument. The omitted second argument is 16 kibibytes. There is no setter and no third constructor.

`CLIENT` and `SERVER` are distinct: they are not the same object and they do not compare equal. A role that is neither `CLIENT` nor `SERVER` is refused and produces no connection.

## `httpwire.__name__`

Attribute on the imported package module `httpwire`. After `import `httpwire``, `__name__` is a text string whose first dotted segment is `httpwire`.

### Shape

`__name__` is a Python text string (`str`). It is not bytes and not a pre-split sequence of path parts. It supports the host string method `split`.

A top-level import `import `httpwire`` reports `__name__` as the text `httpwire`, or as a dotted name whose first segment is `httpwire`. Recovering the package-root segment is:

```
`httpwire`.`__name__`.`split`(".", 1)[0]
```

That first piece equals `httpwire`. It matches the importable package directory name.

## `httpwire.__name__.split`

Bound method on the text stored in `httpwire`.`__name__`. It is the host string split. It is used to recover the package-root segment of `__name__`.

### Signature

```
`split`(sep, maxsplit)
```

The call that recovers the package root is:

```
`split`(".", 1)
```

- The first argument is the period `.`, used as the separator.
- The second argument is the integer 1: at most one split, so any further dots stay in the second piece.

### Return

A sequence of text strings. Index 0 is the package-root segment and equals `httpwire`.

When `__name__` is exactly `httpwire`, the result is a one-element sequence whose only item is `httpwire`. When `__name__` contains a period, index 0 is still `httpwire`.

