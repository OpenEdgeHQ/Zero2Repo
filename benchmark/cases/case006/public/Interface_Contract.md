# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**Optlyn** is a Python package for creating command line interfaces in a composable way with as little code as necessary. It is the “Command Line Interface Composition Kit”: highly configurable, with sensible defaults.

Optlyn in three points:

- Arbitrary nesting of commands
- Automatic help page generation
- Support for lazy loading of subcommands at runtime

The finished product is a **library**, not a command users type. An application author declares commands, groups, options, and arguments; the library parses the process argument list, converts values, generates help, dispatches to the author’s callbacks, and supplies terminal helpers. End users of those applications see a POSIX-style command line: options, positional arguments, nested subcommands, and a help page.

The product parses the caller’s declared interface against the supplied command-line tokens, environment, prompt input, and defaults. It does not fetch remote documents as part of parsing and does not require a network to declare or invoke a command. There is no compiled extension, native code, or accelerator requirement. The library has zero declared runtime dependencies and requires Python 3.10 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient. Documented execution is Linux.

The product is the library, not a particular end-user application. Examples that ship with a repository demonstrate the library; they are not the product. There is no built-in plugin-folder loader and no built-in configuration-file format of the library’s own.

### Shape of the public surface

The product is an **importable Python library**, not a network service and not a wire protocol. It does not ship a required console-script entry of its own; authors publish their own scripts and installed entries that call into the library.

**Distribution and import.** The installable distribution name and the importable top-level package are both `optlyn`. Authors write `import optlyn` or `from optlyn import …` and declare the interface from that package root. Importing the package performs no I/O, starts no processes, and opens no sockets.

**Library.** Decorating a function produces a command object. Invoking that command as a command-line application is standalone mode (the default): usage failures and aborts become process exits with the documented exit codes, and the command’s return value is discarded. When standalone mode is turned off, the same invocation returns to the caller instead of exiting the process: the callback’s return value is available, and failures propagate as exceptions.

A script program invokes the command by calling its `main` entry with no arguments so that the process argument list is used. The same `main` entry also accepts an explicit argument-token list, a program name, and a standalone-mode flag.

**Groups.** A group is a command that dispatches to named subcommands. Authors attach a already-declared command with the group’s `add_command` helper, or declare children on the group. Nested groups are allowed.

**Help.** Every command receives an automatic help option whose default name is `--help`. Asking for that option prints a help page and does not run the command callback. Intentional help exits with status 0.

**Completion.** An installed command, given a reserved environment variable, either prints a shell-specific activation script or prints completion candidates. Completion is available when the command is invoked as an executable entry, not when it is run as `python script.py`. The installed entry runs the command’s `main`. When that reserved variable holds a `{shell}_complete` instruction, complete mode reads `COMP_WORDS` and `COMP_CWORD`: `COMP_WORDS` is a single space-joined string that includes the executable name; for bash, zsh, and powershell, `COMP_CWORD` is the integer index of the incomplete word (or the next slot when the incomplete token is empty); for fish, `COMP_CWORD` is the incomplete token string itself, which may be empty. Registration-script syntax, file/dir protocol tokens, and suggestion-stream frame separators are not pinned.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Naming conventions

**Product and package.** The product identity is Optlyn. The distribution and the import package are spelled `optlyn`.

**Command names.** Decorating a function with no extra arguments produces a command whose name is the function name converted to lowercase, with underscores replaced by dashes, and with a trailing `_command`, `_cmd`, `_group`, or `_grp` suffix stripped when present (longest match first). A function whose name is two words joined by an underscore is therefore invoked with those words joined by a dash. Passing an explicit name uses that name instead. After an explicit name is set, the mapped dashed name is not accepted.

**Options.** A name with two leading dashes is a long option. A name with one leading dash and one character is a short option. Long options may take a value as `--name=value` or `--name value`. Alternative prefixes such as `/` and `+` are accepted when the author declares them. Combined short options of a single character are supported. Multi-character short names are not supported.

**Destination inference.** When the author does not give a destination name, it is inferred from the declared option names: a name that is already a valid identifier wins; otherwise the first long name; otherwise the first short name. A leading dash prefix is stripped and remaining dashes become underscores, so a long name of two words joined by a dash delivers to a two-word identifier joined by an underscore.

**Automatic help.** Help-option names default to `--help`.

**Placeholders.** The default metavar for an argument is the argument name in uppercase. For an option that takes a value, the default metavar is the type name in uppercase, unless that type supplies its own placeholder; a flag or counting option has no metavar. Exact metavar punctuation is not pinned. Optional elements on the usage line are bracketed; required elements are not.

### Global observables an implementer must reproduce

**Process exits (standalone mode).**

- A successful command-line run (callback completed, or intentional `--help`) exits with status 0.
- Usage errors — unknown option, unknown subcommand, missing required parameter, conversion failure, leftover tokens that are not allowed — exit with status 2. A message is written to standard error. The command callback does not run.
- Abort and other library-signaled user errors that are not usage errors exit with status 1.

When standalone mode is off, those same conditions do not exit the process: the caller receives the failure, abort, or callback return value.

**Deprecation.** A command marked deprecated still runs and still exits 0 on success. On invocation the library emits a deprecation warning that is distinguishable from ordinary command output and from a usage failure. A custom deprecation note, when the author supplies one, appears in that warning. The help page of a deprecated command is distinguishable from the help page of an otherwise identical non-deprecated command. Exact wording of the warning and of the help mark is not pinned.

**Unicode and locale.** Command-line values are text. An ASCII-only environment encoding does not abort invocation: the same command still runs and produces the same successful outcome as in a Unicode locale.

**No product config file.** A default map can be loaded from whatever the author chooses. The library does not parse a configuration-file syntax of its own and does not require a config file to be present.

**Thread locality.** The current invocation context is visible to code running on the same thread. Another thread does not see that context unless the author re-enters the same context in that thread.

## `allow_extra_args`

Boolean invocation-context flag. Authors set it as the `allow_extra_args` key of a `context_settings` mapping passed to `command` (or `group`). The same name is accepted on the invocation `Context`.

When `allow_extra_args` is true, leftover undeclared tokens beyond declared arity are not a usage failure: the callback still runs. The declared argument still receives only the tokens that fill its arity; leftover tokens are not bound into that value. When the key is omitted or not true, leftover undeclared tokens are a usage failure (standalone mode exits 2, callback not run), unless a variadic `nargs=-1` argument collects them.

An option-shaped token (a leading dash, with no preceding `--` separator) is not a leftover undeclared argument under this flag alone. That token remains a usage failure even when `allow_extra_args` is true. Consuming such a token as a declared argument requires `ignore_unknown_options` or a leading `--`.

## `ignore_unknown_options`

Boolean invocation-context flag. Authors set it as the `ignore_unknown_options` key of a `context_settings` mapping passed to `command` (or `group`). The same name is accepted on the invocation `Context`.

When `ignore_unknown_options` is true, option-shaped tokens may be consumed as declared arguments without a leading `--` separator: the callback still runs. When the key is omitted, those tokens are a usage failure (standalone mode exits 2, callback not run).

A leftover option-shaped token beyond declared arity is still a usage failure even when `ignore_unknown_options` is true, unless leftover undeclared tokens are allowed by `allow_extra_args`.

Unknown long options are left intact as leftover tokens. Unknown short options may be split: a known short inside a stacked short token is consumed, and the unknown remainder stays leftover. A variadic argument can collect those leftover option-like tokens.

## `optlyn`

The importable top-level package is `optlyn`. Authors declare the interface from this package root (`from `optlyn` import …`). Importing the package performs no I/O, starts no processes, and opens no sockets.

These names are importable as ``optlyn`.<name>` and as `from `optlyn` import <name>`:

- `Path`
- `STRING`
- `argument`
- `command`
- `group`
- `option`

Typical import used to declare a command or group and attach parameters:

```
from `optlyn` import `STRING`, `Path`, `argument`, `command`, `group`, `option`
```

A script that only needs a subset may import that subset, for example `from `optlyn` import `command``.

## `optlyn.BOOL`

Import `BOOL` from the package root (`from `optlyn` import `BOOL``). Built-in boolean parameter type. Attach it as `type=BOOL` on an `option`.

### Conversion

Accepts a text token and delivers a Python boolean to the destination — not a string. The delivered value is boolean true or boolean false (`is` identity with those constants), not a truthy or falsy string.

Matching is case-insensitive. These tokens are true: `1`, `true`, `t`, `yes`, `y`, `on`. A mixed-case token such as `True` is true. These tokens are false: `0`, `false`, `f`, `no`, `n`, `off`. A mixed-case token such as `OFF` is false.

When an option’s declared `default` is a boolean and the author does not set `type`, the library infers this conversion: a token such as `off` is delivered as false. An explicit `type=STRING` keeps that token as text.

A token that is none of those words is a usage failure: standalone mode exits with status 2, and the command callback does not run.

### Flags

A boolean flag declared `is_flag=True` uses this conversion without attaching `type=BOOL`. Presence of the flag (flag alone, no following token) delivers true; omitting the flag delivers false.

## `optlyn.BadParameter`

Import `BadParameter` from the package root (`from `optlyn` import `BadParameter``). Exception class used to refuse a converted parameter value from a parameter callback.

### Signature

```
`BadParameter`(message)
```

- `message` — text describing why the value is refused. A string is accepted.

A single string argument is enough. Authors do not have to name the parameter; the library attaches that context when it handles the exception.

### Refusal from a parameter callback

A parameter callback is the callable attached to an `option` as `callback`. The library invokes it with three positional arguments: the invocation context, the parameter, and the already-converted value — including when the parameter was omitted. The invocation context exposes `params`, a mapping of destinations already bound on this invocation. A later parameter’s callback may read an earlier destination from that mapping (so a missing parameter can default from an earlier value). It may return a replacement value, or it may raise `BadParameter`.

- When the callback returns a value, that returned value is what the command callback receives at the option’s destination, in place of the converted token.
- When the callback raises `BadParameter`, the value is refused: that is a usage error. Standalone mode exits with status 2. A message is written to standard error that distinguishes the failure from success. The command callback does not run, and the refused value is not delivered. Exact wording of that message is not pinned.

The same callback still runs when the value came from a named `envvar`, from the invocation `default_map`, or from a `prompt`, not only from the command line. On a repeatable option (`multiple=True`) it is invoked once with the whole gathered sequence.

## `optlyn.Choice`

Import `Choice` from the package root (`from `optlyn` import `Choice``). Constructible parameter type for a closed list of allowed values. Attach an instance to an `option` as that parameter’s `type`.

### Signature

```
`Choice`(choices)
`Choice`(choices, `case_sensitive`=True)
```

- `choices` — allowed values. A list of strings is accepted. An enumeration class is also accepted: the allowed tokens are that enumeration’s member names.
- `case_sensitive` — when true (including when omitted), matching is case-sensitive. `case_sensitive=False` makes matching ignore case.

Returns a type instance. Pass that instance to `option` as `type`, the same attachment used for `type=STRING` and `type=INT`.

### Converted value

The value delivered is the original choice object (the originally registered list entry, or the enumeration member), not merely the matched string. With `case_sensitive=False`, an exact-case token and a case-folded twin of a registered entry both deliver that original object. The folded token itself is not delivered. An enumeration member remains that member, including its name and value.

If two registered entries normalize to the same token when `case_sensitive` is false, a matching input delivers the first registered original, not a later colliding original.

An unknown token is a usage failure: standalone mode exits with status 2, and the command callback does not run.

A repeatable option (`multiple=True`) may be typed `Choice`. A declared `default` for that option must be a sequence of valid choices; omitting the option delivers those original entries in order.

### Help listing

A value option typed `Choice` lists its allowed values on the `--help` page. After the option’s public name and help string are removed from the option’s help record, that remainder still contains the registered choice strings. Distinct closed lists produce distinct remainders. An otherwise identical option typed `STRING` does not list those choice strings. Exact metavar punctuation is not pinned.

## `optlyn.CommandCollection`

Import `CommandCollection` from the package root (`from `optlyn` import `CommandCollection``). Group class that presents the union of subcommands gathered from several source groups under one dispatch surface. Authors pass it as `cls` to `group` together with those sources.

### Signature

```
`CommandCollection`(name=None, sources=None, **kwargs)
```

- `name` (`str` or `None`) — same rules as `Group`.
- `sources` — a list of groups whose children this collection exposes. `None` (the default) is an empty list.
- `kwargs` — the same group and command keywords `group` forwards to a group class (including the decorated callback).

Authors do not have to call this constructor themselves. This form builds the collection and uses the decorated function as its callback:

```
`group`(cls=`CommandCollection`, `sources`=[…])(callback)
```

The constructed object is an instance of `CommandCollection`. Each entry in `sources` is a group that already has children registered on it. The collection’s listing and lookup are the union of those sources’ children. Changing which groups are passed as `sources` changes which names are listed and which names dispatch.

### Union dispatch

A name that exists on any source is accepted as the next token. Invoking that name runs that source child’s callback and does not run a child of a different name on another source.

An unknown name is a usage failure that does not use the no-arguments help page: standalone mode exits 2, the collection callback does not run, and no source child runs.

### Help and empty arguments

The collection is a group class, so the group empty-argument and help rules apply to **this** collection’s callback and description, not to a source group’s callback or description.

Invoking the collection with no extra arguments is the missing-subcommand help page: standalone mode exits 2, the collection callback does not run, the collection’s description is shown, and no source child runs.

`--help` on the collection is intentional help: standalone mode exits 0, the collection callback does not run, the collection’s description is shown, and the exported names of the union appear on the page. A name that is only on a source that was not passed to this collection does not appear.

## `optlyn.Context`

Import `Context` from the package root (`from `optlyn` import `Context``). Invocation-context class. The library constructs one instance per invocation and passes that instance to author callbacks that request it (including the callback given to `custom_version_option`). Authors do not need to construct it themselves.

Extra keywords forwarded from `main` are accepted by this constructor. Names used that way include `help_option_names`, `show_default`, `terminal_width`, `max_content_width`, and `token_normalize_func`.

### `token_normalize_func`

A function forwarded from `main` onto this invocation context. It applies to option names, choice values, and command names. A lowercase function makes an uppercased option name, choice value, or command name match the declared form and the callback runs. An identity function, or omitting the extra, leaves that uppercased token a usage failure (standalone mode exits 2, callback not run). A token that still does not match after the function is a usage failure.

### `help_option_names`

List of strings that name the automatic help option. The default is a one-element list containing `--help`. Replacing the list replaces those names: a token from the new list prints the help page, exits 0, and does not run the command callback; a former name that is no longer in the list is an unknown option (standalone mode exits 2; the help-page description is not printed).

If an author-declared option reuses every name in this list, the automatic help option is dropped and the author’s option runs. If the author reuses only some of the names, a remaining automatic name still prints help and exits 0. Reusing only `--help` while the list is `--help` and `-h` still leaves `-h` as successful help.

### `show_default`

When `True` on the invocation, help shows each option’s default as if that option had `show_default=True`. When omitted or not true, defaults stay hidden unless the option itself enables show-default.

### `terminal_width` and `max_content_width`

Help text is rewrapped to a content width.

- When `terminal_width` is omitted, the width is auto-detected and then capped by `max_content_width`. `max_content_width` defaults to 80: omitting it, or passing `None`, uses that same cap. An omitted-width run of a long description therefore wraps, and no rendered description line exceeds 80 columns.
- When `terminal_width` is supplied, that value is the wrap width as-is. The default 80-column cap does not apply. A long description still wraps, and no rendered description line exceeds the supplied width; lines may be longer than 80.
- Raising `max_content_width` to the same value as an explicit `terminal_width` does not change that explicit-width rule: the supplied terminal width remains the wrap bound.
- Raising `max_content_width` on an omitted-width run lengthens auto-detected lines past the default 80-column bound.

A narrower explicit `terminal_width` produces shorter description lines than an omitted-width run of the same command.

## `optlyn.DateTime`

Import `DateTime` from the package root (`from `optlyn` import `DateTime``). Constructible parameter type that parses a token into a date-time value. Attach an instance to an `option` as that option’s `type`.

### Signature

```
`DateTime`()
`DateTime`(`formats`=...)
```

- `formats` — a sequence of date format strings, tried in order. Omitting the argument (the no-argument constructor) selects the built-in list.

Returns a type instance. Pass that instance to `option` as `type`, the same attachment used for `type=STRING` and `type=INT`.

### Default formats

The default list is the finite set: date `YYYY-MM-DD`; date and time with `T` as `YYYY-MM-DDTHH:MM:SS`; date and time with a space as `YYYY-MM-DD HH:MM:SS`. The delivered value exposes year, month, and day; a token that includes a time also exposes hour, minute, and second. Values parsed under these defaults are not timezone-aware (`tzinfo` is absent).

An explicit `type=STRING` keeps the same token as text.

### Author formats

The author may replace that list by passing `formats`. Formats are tried in order; the first success wins. A token that can be read two ways (for example `%d-%m-%Y` then `%m-%d-%Y` versus the reverse) is parsed with the first matching format.

Author-supplied strings such as `%d/%m/%Y`, `%d-%m-%Y`, and `%m-%d-%Y` are accepted. After a replacement list, a token that matches only a default format and not the replacement is refused.

### Conversion failure

A token that matches none of the formats is a usage failure: standalone mode exits with status 2, and the command callback does not run.

## `optlyn.FLOAT`

Import `FLOAT` from the package root (`from `optlyn` import `FLOAT``). Built-in floating-point parameter type. Attach it as `type=FLOAT` on an `option`.

### Conversion

Accepts a floating-point token and delivers a Python `float` to the destination — not a string. Arithmetic on that value (for example doubling) succeeds.

When an option’s declared `default` is a float and the author does not set `type`, the library infers this conversion: the same token is delivered as a float. An explicit `type=STRING` keeps that token as text.

A token that is not a floating-point number is a usage failure: standalone mode exits with status 2, and the command callback does not run.

## `optlyn.File`

Import `File` from the package root (`from `optlyn` import `File``). Constructible parameter type that opens a file. The converted value is an open file, not a path. Attach an instance to an `argument` or an `option` as that parameter’s `type`.

### Signature

```
`File`()
`File`("r")
`File`("w")
`File`("rb")
`File`("wb")
`File`("w", `encoding`="latin-1")
`File`("r", `encoding`="latin-1")
`File`("w", `lazy=True`)
`File`("w", `lazy=False`)
`File`("w", `atomic=True`)
`File`("w", `atomic=False`)
```

No arguments are required. The no-argument form opens for reading text, the same as `r`. Returns a type instance. Pass that instance to `argument` or `option` as `type`, the same attachment used for `type=STRING`, including as `type=File()`.

The first argument is the open mode:

- `r` — read text. A read returns a Python `str`. The file on disk is not rewritten.
- `w` — write text. A write accepts a Python `str`.
- `rb` — read binary. A read returns Python `bytes`, including when the token is `-` (standard input).
- `wb` — write binary. A write accepts Python `bytes`. Contents written through the handle are stored on that path as those bytes.

Keyword arguments accepted together with that mode:

- `encoding` — text codec used to decode or encode when the mode is text. When the author sets it, that codec is used for a real path and for the dash token. A write with a declared codec stores that codec’s bytes on disk, not UTF-8 of the same text. A later read with the same codec, including from `-`, recovers that text. Text modes still deliver and accept text when this argument is omitted.
- `lazy` — `lazy=True` delays opening until first I/O. `lazy=False` opens before the callback runs. When omitted, reading and the dash token open immediately; writing a real path waits until first I/O.
- `atomic` — `atomic=True` writes to a sibling temporary file and replaces the target when the handle is closed. `atomic=False`, and omitting the argument, do not use that replace-on-close protocol. Temporary names are not pinned.

### Converted value

The callback receives an open file under the parameter’s destination. That object can be read, written, and flushed according to the mode. It is not a filesystem path and is not filesystem path text.

### Dash token

The token `-` means standard input when the file is opened for reading and standard output when opened for writing. The same rule applies on an `argument` and on an `option`, and in text and binary modes. After the command callback returns, a dash write still leaves standard output usable: further writes to standard output still appear.

### Immediate open and lazy write

A missing read target is a usage failure before the callback runs: standalone mode exits with status 2, the path appears on standard error, and the callback does not run. Exact wording of the message is not pinned.

A write-mode file whose `lazy` is omitted or `lazy=True` does not truncate the target if the callback never uses the handle. The original contents remain. Writing through the handle then stores what was written.

A write-mode file with `lazy=False` is opened before the callback runs. Even if the callback never uses the handle, the original contents are not preserved. A path that cannot be opened (including a directory given as a write target) is a usage failure before the callback runs: standalone mode exits with status 2, the path appears on standard error, and the callback does not run.

A write-mode file that is lazy (omitted or `lazy=True`) may be bound to an unopenable path without failing if the callback never uses the handle: the command succeeds. If the callback then writes, that is a general file-open failure, not a usage failure: standalone mode exits with status 1, the callback has already started, the path appears on standard error, and work after that write does not run. Exact wording of the message is not pinned. The exception class is not pinned.

Distinct unopenable paths produce distinct standard-error text: the report identifies the path that failed.

### Atomic write

With `atomic=True`, after a write and a flush, an independent reader of the original path still sees the original contents. After the handle is closed (the command returns), the original path holds the written contents.

With `atomic=False`, and when `atomic` is omitted, the original path holds the written contents after the command returns.

### Environment lists

When an option is repeatable (`multiple=True`) and typed `File` (`type=File()`), a non-empty environment value named by `envvar` is split on the platform path separator, not on whitespace. On Unix that separator is a colon. Each piece is opened as one file in the sequence delivered to the option’s destination, in left-to-right order. An otherwise identical repeatable option typed `STRING` does not split that value on the path separator.

## `optlyn.FloatRange`

Import `FloatRange` from the package root (`from `optlyn` import `FloatRange``). Constructible floating-point parameter type that must lie in an optional minimum/maximum range. Attach an instance to an `option` as that option’s `type`.

### Signature

```
`FloatRange`(`min`=None, `max`=None, `min_open`=False, `max_open`=False, `clamp`=False)
```

- `min` — lower bound. Omitted (`None`) means unbounded below.
- `max` — upper bound. Omitted (`None`) means unbounded above.
- `min_open` — when true, the lower bound is excluded.
- `max_open` — when true, the upper bound is excluded.
- `clamp` — when true, a value outside the range is replaced by the nearest included boundary instead of failing. Clamp is only allowed when both bounds are closed.

Returns a type instance. Pass that instance to `option` as `type`, the same attachment used for `type=FLOAT`.

### Conversion

Accepts a floating-point token and delivers a Python float to the option’s destination. Bounds are closed by default: the minimum and the maximum are accepted. An open lower bound refuses the minimum and accepts a value inside the range. An open upper bound refuses the maximum and accepts a value inside the range. A bound that is omitted does not constrain that side.

Without clamp, a value outside the range is a usage failure: standalone mode exits with status 2, and the command callback does not run.

With clamp and closed bounds, a value above the range is replaced by the maximum; a value below the range is replaced by the minimum; a value already inside is unchanged.

### Open bounds and clamp

Declaring `clamp=True` together with `min_open=True` or `max_open=True` is refused: constructing that type (including when an `option` declaration instantiates it) raises and no command is produced. Closed bounds with clamp remain accepted.

## `optlyn.Group`

Import `Group` from the package root (`from `optlyn` import `Group``). Group class: a command that holds named subcommands, which may themselves be groups. `group` instantiates this class when `cls` is omitted. Authors subclass `Group` and override listing and lookup; passing that subclass as `cls` to `group` produces an instance of the subclass (`isinstance` of that subclass is true).

### Signature

```
`Group`(name=None, invoke_without_command=False, no_args_is_help=None, chain=False, **kwargs)
```

- `name` (`str` or `None`) — exported name of this group. `None` derives it from the callback the same way `command` does.
- `invoke_without_command` (`bool`, default `False`) — when `True`, a run with no child still runs this group’s callback.
- `no_args_is_help` (`bool` or `None`, default `None`) — when `None`, defaults to the opposite of `invoke_without_command`. `True` (the default when `invoke_without_command` is `False`) makes an empty extra-argument list the missing-subcommand help page. `no_args_is_help=False` makes that empty list a usage failure that does not print that help page.
- `chain` (`bool`, default `False`) — when `True`, this group is a chaining group.
- `kwargs` — forwarded to the command constructor. Names used that way include the callback function, `hidden`, and the same command keywords `command` accepts.

Authors do not have to call this constructor themselves. `group` builds the instance and supplies the decorated function as the callback. A subclass that calls the base constructor with `*args, **kwargs` accepts whatever `group` forwards.

### Attribute

- `callback` — the author function this group runs. A group built by `group` exposes that function. The value may be passed to `group` again to build another group with the same callback.

### `add_command`

```
`add_command`(cmd, name=None)
```

Registers an already-built command (or nested group) on this group.

- `cmd` — the child to attach.
- `name` (`str` or `None`) — exported name the parent accepts as the next token. When omitted, the child’s own name is used.

A later-registered child is invoked the same way as one attached at declaration, including when registration happens in another module after the group was created. After an explicit name is set, a different mapped name derived from the function is not accepted.

Attaching a nested group under a group declared with `chain=True` is refused at declaration: `add_command` raises and the nested group is not registered. Attaching a leaf command to that same chaining group is accepted. A group that is not chaining accepts nested groups.

### Instance `command` helper

```
`command`(name=None, **attrs)
```

A method on the group instance. Calling it with the same arguments accepted by the package-root `command` decorator returns a decorator. Applying that decorator to a function builds the child and registers it immediately on this group. An explicit `name` is the exported child name; after it is set, the function’s mapped dashed name is not accepted. The helper and `add_command` are interchangeable at invocation.

### `result_callback`

```
`result_callback`()
```

A no-argument call that returns a decorator. Applying that decorator to a function registers the function as this group’s result processor.

Registration is optional. Without it, dispatched children still run and the unregistered function does not.

When registered, the function runs after the dispatched children: child callback output appears before this processor’s output. It is called with the collected return value as its first positional argument. This group’s own parameter destinations are passed as keywords: the converted value for a declared option destination is present under that destination name.

**Chain mode** (`chain=True`):

- Named children: the first positional argument is a positional sequence of those children’s return values in command-line order. Swapping the child names on the command line swaps the positions in that sequence. The Python type of the sequence is not pinned.
- No child, with `invoke_without_command=True`: the first positional argument is an empty positional sequence, not this group’s own return value. The processor runs; the run is not the missing-subcommand help page.
- No child, when `invoke_without_command` is omitted or false (the default): the missing-subcommand usage help; the processor does not run.

**Non-chain mode** (`chain=False`):

- A named child: the first positional argument is that child’s return value.
- No child, with `invoke_without_command=True`: the first positional argument is this group’s own return value. It is not an empty sequence.

A file opened as a chained child’s parameter is closed when that child’s callback returns, so the result processor cannot use that handle. A file opened as this group’s own parameter remains readable in the result processor.

When `chain=True` and standalone mode is off, the invocation itself returns that same positional sequence of the dispatched children’s return values in command-line order, even when no `result_callback` is registered. Swapping the child names on the command line swaps the positions in that returned sequence. The Python type of the sequence is not pinned. That return is not this group’s own callback return. A standalone run of the same chain exits 0.

On a chaining group, a consume-rest argument on a non-last child is accepted at declaration and then consumes remaining tokens, so later child names are not dispatched. A consume-rest argument on the last child still lets earlier children run.

### `list_commands` and `get_command`

```
`list_commands`(ctx)
`get_command`(ctx, cmd_name)
```

The supported extension points for custom listing and lookup. Authors override these on a `Group` subclass.

- `ctx` — the invocation context for this group.
- `cmd_name` — the child name being resolved.

`list_commands` returns a list of exported child names. The default implementation returns the names registered on this group. A subclass override’s return value is the list used on this group’s help page: each returned name appears there (unless the resolved child is hidden). Complete mode consults that same override: with an empty incomplete token, the suggestion stream contains those returned names even when no child was registered with `add_command`. The command callback does not run. Completing at this group does not load a grandchild that would be resolved only after a listed child is selected.

`get_command` returns the child command for that name, or `None` when there is no such child. The default implementation returns the command registered under that name. Dispatch calls this with the token the user typed. Help calls `list_commands` and then `get_command` for each listed immediate name so it can show those children; it does not resolve grandchildren.

A subclass may return a command loaded only when that name is requested. Looking up one name does not look up an unrequested sibling. A child resolved this way is invoked the same as one attached with `add_command`. Returning `None` for the typed token is an unknown-subcommand usage failure: standalone mode exits with status 2, the group callback does not run, no child runs, and the page is not the no-arguments help page.

### Named dispatch and nesting

The next token after this group’s own parameters is the child name. Only the matching child’s callback runs. Unmatched siblings do not run.

The group callback **does** run when a named child is dispatched, and it runs before that child. Nested groups run outside-in: each group on the path runs, then the next, then the leaf. A grandchild is unreachable unless every middle group on the path is named. Skipping a middle name is an unknown-subcommand usage failure on the group that was invoked; that group’s callback does not run, and neither the skipped middle nor the leaf runs.

Parameters belong to the command that declared them. A group option or argument is delivered only to that group’s callback and must appear before the child name. A child option appears after that name and is delivered only to the child. Values do not leak across layers. A group argument followed by a child name binds the argument and then dispatches.

On a group, mixing is off by default: the subcommand name ends that group’s own option parsing, so a group option after the subcommand name is not delivered to the group callback.

### Empty arguments, leftover-empty, and unknown names

By default, invoking the group with no extra arguments does not run the group callback. It prints the group’s help page as a usage failure (standalone mode exits with status 2). The page includes the group’s description. No child runs.

`--help` on the group itself is intentional help: the same description is printed, the group callback does not run, no child is dispatched, and standalone mode exits 0.

An unknown child name is a usage failure that does not use the no-arguments help page: standalone mode exits 2, a usage report is written to standard error, the group description from that help page is absent, and neither the group callback nor any child runs.

A parsed run that consumes this group’s options or arguments and then has no child name is the same leftover-empty usage failure: not the no-arguments help page, group callback not run, no child run, standalone mode exits 2.

Invoking a nested group by name with no further child still runs every outer callback already on the path, then that nested group’s no-arguments help page (that nested group’s description, not an outer description). The nested group’s callback does not run.

`invoke_without_command=True`: a run with no extra arguments runs the group callback and exits 0. No child runs. A named child still runs the group callback first, then the child.

`no_args_is_help=False`: a run with no extra arguments is the leftover-empty usage failure (status 2, no help page), not the no-arguments help page.

### Child help and version

A named child followed by `--help` is help for that child: the group callback still runs, the child callback does not, the child’s page text is printed, and standalone mode exits 0.

`--help` before the child name is help for the group: the group callback does not run, the child does not run, and the child’s page-only text is absent.

A named child followed by `--version` still runs the group callback, does not run the child callback, prints the version identity, and exits 0.

Group-level `--help` or `--version` skips the group callback and does not dispatch.

### Hidden children

`hidden=True` on a child command or nested group omits that child’s exported name from the parent’s help page. The parent still accepts that name as the next token and dispatches into it, including a further nested leaf under a hidden middle group.

## `optlyn.INT`

Import `INT` from the package root (`from `optlyn` import `INT``). Built-in integer parameter type. Attach it as `type=INT` on an `option` or an `argument`.

### Conversion

Accepts an integer token and delivers a Python `int` to the destination — not a string. Arithmetic on that value (for example multiplying and adding) succeeds. A dotted token such as a whole number followed by `.5` is not an integer.

When a parameter’s declared `default` is an integer and the author does not set `type`, the library infers this conversion: the same token is delivered as an integer. An omitted `type` with no integer default, or an explicit `type=STRING`, keeps a numeric-looking token as text.

A token that is not an integer is a usage failure: standalone mode exits with status 2, and the command callback does not run. The usage report identifies the offending parameter (the option’s public name, or the argument’s destination). A sibling parameter that did not fail is not named in that report.

## `optlyn.IntRange`

Import `IntRange` from the package root (`from `optlyn` import `IntRange``). Constructible integer parameter type that must lie in an optional minimum/maximum range. Attach an instance to an `option` as that option’s `type`.

### Signature

```
`IntRange`(`min`=None, `max`=None, `min_open`=False, `max_open`=False, `clamp`=False)
```

- `min` — lower bound. Omitted (`None`) means unbounded below.
- `max` — upper bound. Omitted (`None`) means unbounded above.
- `min_open` — when true, the lower bound is excluded.
- `max_open` — when true, the upper bound is excluded.
- `clamp` — when true, a value outside the range is replaced by the nearest included boundary instead of failing.

Returns a type instance. Pass that instance to `option` as `type`, the same attachment used for `type=INT`.

### Conversion

Accepts an integer token and delivers a Python `int` to the option’s destination. Bounds are closed by default: the minimum and the maximum are accepted. An open lower bound refuses the minimum and accepts the next included integer. An open upper bound refuses the maximum and accepts the previous included integer. A bound that is omitted does not constrain that side.

Without clamp, a value outside the range is a usage failure: standalone mode exits with status 2, and the command callback does not run.

With clamp, a value above the range is replaced by the nearest included upper bound; a value below the range is replaced by the nearest included lower bound; a value already inside is unchanged. When the lower bound is open and clamp is enabled, a token equal to that excluded minimum is replaced by the next included integer.

## `optlyn.ParamType`

Import `ParamType` from the package root (`from `optlyn` import `ParamType``). Base class for parameter types. Authors subclass it to supply a custom type and attach an instance as `type` on an `option`, an `argument`, or `prompt`.

### Custom type

A subclass sets a descriptive `name` and implements `convert`:

```
`convert`(value, `param`=None, `ctx`=None)
```

- `value` — the token to convert, or a value that is already the right type.
- `param` — the parameter using this type. May be omitted.
- `ctx` — the invocation context. May be omitted.

`convert` must convert a string to a value. It must pass through a value that is already the right type, so a declared default that is already converted is delivered unchanged. It must convert when `param` and `ctx` are omitted (prompt-time conversion, including a direct `prompt` call with no command).

### Conversion function

A conversion function is also accepted as a `type`. The function receives the token and returns the converted value. Raising `ValueError` refuses the token. That refusal is a usage failure: standalone mode exits with status 2, and the command callback does not run.

### Conversion failure

Failure of conversion on a declared parameter is a usage error that identifies the offending parameter (the option’s public name, or the argument’s destination). Standalone mode exits with status 2. The command callback does not run. A sibling parameter that converted successfully is not named, and its converted value is not delivered. Exact wording of the usage message is not pinned.

## `optlyn.Path`

Import `Path` from the package root (`from `optlyn` import `Path``). Constructible parameter type for a filesystem path. The converted value is the path itself, not an open file. Attach an instance to an `argument` or an `option` as that parameter’s `type`.

### Signature

```
`Path`()
`Path`(`exists=True`)
`Path`(`exists=False`)
`Path`(`exists=True`, `file_okay=True`, `dir_okay=False`)
`Path`(`exists=True`, `file_okay=False`, `dir_okay=True`)
`Path`(`exists=True`, `file_okay=True`, `dir_okay=True`)
`Path`(`exists=True`, `executable=True`, `readable=False`)
`Path`(`exists=True`, `readable=True`)
`Path`(`exists=True`, `writable=True`, `readable=False`)
`Path`(`exists=True`, `readable=True`, `executable=False`)
`Path`(`exists=False`, `readable=True`, `writable=True`, `executable=True`)
`Path`(`exists=True`, `readable=True`, `writable=True`, `executable=True`)
`Path`(`resolve_path=True`)
`Path`(`resolve_path=False`)
`Path`(`exists=True`, `allow_dash=True`)
`Path`(`exists=True`, `allow_dash=False`)
`Path`(`path_type`=str)
```

No arguments are required. Returns a type instance. Pass that instance to `argument` or `option` as `type`, the same attachment used for `type=STRING`, including as `type=Path()`.

The no-argument form does not require the path to exist and does not open the path. A path token is delivered as path text — the same string the command line or environment supplied — not as an opened file.

Keyword arguments. Each check is independently selectable:

- `exists` — `exists=True` requires the path to be present. A present path is accepted. A missing path is a usage failure: standalone mode exits with status 2, and the command callback does not run. On an `option`, that failure names the option’s public flag on standard error. Two otherwise identical options with different public names produce different remainders after the missing path is stripped from the message. On an `argument`, that failure names the argument’s destination; case of that destination token is not pinned. `exists=False`, and omitting the argument, does not require the path to exist.
- `file_okay` and `dir_okay` — file versus directory allowance. With `exists=True`, `file_okay=True`, and `dir_okay=False`, a present file is accepted and a directory is a usage failure that names the option. With `exists=True`, `file_okay=False`, and `dir_okay=True`, a present directory is accepted and a file is a usage failure that names the option. With `exists=True`, `file_okay=True`, and `dir_okay=True`, a present file and a present directory are both accepted.
- `readable` — with `exists=True` and `readable=True`, an unreadable present path is a usage failure that names the option; a readable present path is accepted. `readable=False` does not impose that readable check.
- `writable` — with `exists=True` and `writable=True`, an unwritable present path is a usage failure that names the option; a writable present path is accepted.
- `executable` — with `exists=True` and `executable=True`, a non-executable present path is a usage failure that names the option; an executable present path is accepted. `executable=False` together with `readable=True` accepts a present readable non-executable file.
- `resolve_path` — `resolve_path=True` delivers an absolute path. A symlink is followed: the delivered value is the real path of the target. A leading tilde in the token is not expanded to the home directory. `resolve_path=False` does not replace a symlink token with its real path.
- `allow_dash` — with `exists=True` and `allow_dash=True`, the token `-` is accepted as the path `-` and is not opened: standard input is not consumed. With `exists=True` and `allow_dash=False`, the token `-` is a usage failure when no file of that name exists; if a file named `-` exists, that token is accepted as the path `-` and still does not consume standard input. An otherwise identical `File` read of `-` does consume standard input.
- `path_type` — the class used to produce the delivered value. `str` delivers a Python `str`. The pathlib path class delivers a pathlib path instance. The filesystem path of either object is the supplied token.

Exact wording of usage messages is not pinned.

### Converted value

The callback receives a path under the parameter’s destination. That object is not an open file. Unless `resolve_path=True` rewrites it as described above, the filesystem path of the value is the supplied token.

### Missing paths and further checks

When `exists=False`, a missing path is accepted even if `readable=True`, `writable=True`, and `executable=True` are also set: those permission checks are not applied to a missing path. The same permission checks with `exists=True` still refuse a present path that fails them.

### Environment lists

When an option is repeatable (`multiple=True`) and typed `Path` (`type=Path()`), a non-empty environment value named by `envvar` is split on the platform path separator, not on whitespace. On Unix that separator is a colon. Each piece is one path value in the sequence delivered to the option’s destination, in left-to-right order. Each piece is delivered as a path, not as an opened file.

When a variadic argument (`nargs=-1`) is typed `Path` (`type=Path()`), a non-empty environment value named by `envvar` is split on the platform path separator, not on whitespace. On Unix that separator is a colon. Each piece is one path value in the sequence delivered to the argument’s destination, in left-to-right order. An otherwise identical variadic argument that is not typed `Path` splits that value on whitespace instead.

## `optlyn.STRING`

Import `STRING` from the package root (`from `optlyn` import `STRING``). Built-in Unicode-text parameter type. Attach it to an argument as `type=STRING`.

An argument typed `STRING` stays text. A supplied token is delivered as that string, including when the characters look like an integer. An otherwise identical argument whose integer `default` infers integer conversion delivers an integer instead.

## `optlyn.Tuple`

Import `Tuple` from the package root (`from `optlyn` import `Tuple``). Constructible parameter type for a fixed-length product of inner types, one converted value per position. Attach an instance to an `option` as that option’s `type`.

### Signature

```
`Tuple`(types)
```

- `types` — a sequence of inner types, one per position. A two-element list of `INT` then `FLOAT` is accepted.

Returns a type instance. Pass that instance to `option` as `type`, the same attachment used for `type=STRING` and `type=INT`.

### Arity and conversion

Attaching `type=Tuple([INT, FLOAT])` to an option sets that option’s arity to two (the length of the inner-type sequence). The option consumes that many tokens per occurrence. The author does not need to declare a separate token count.

Each token is converted with the inner type at that position:

- the first token with `INT`, delivered as a Python `int` (not a string)
- the second token with `FLOAT`, delivered as a Python `float` (not a string)

The command callback receives an indexable two-element sequence at the option’s destination: the first element supports integer arithmetic; the second supports floating-point arithmetic.

A token that the inner type at that position cannot convert is a usage failure: standalone mode exits with status 2, and the command callback does not run.

## `optlyn.UNPROCESSED`

Import `UNPROCESSED` from the package root (`from `optlyn` import `UNPROCESSED``). Built-in pass-through parameter type. Attach it as `type=UNPROCESSED`, including on a variadic `argument` (`nargs=-1`).

### Conversion

Does not convert the token. A numeric-looking token stays text: it is not turned into an integer. On a variadic argument the destination receives a sequence of those original tokens.

The same token on an otherwise identical parameter typed `INT` is delivered as a Python integer.

## `optlyn.UUID`

Import `UUID` from the package root (`from `optlyn` import `UUID``). Built-in UUID parameter type. Attach it as `type=UUID` on an `option`.

### Conversion

Accepts UUID text and delivers a UUID value to the destination — not the token string. That value is not a string; it exposes hex and int.

This type is never inferred from a default. When the author sets a UUID default and does not attach `type=UUID`, a UUID-text token is delivered as text.

A token that is not UUID text is a usage failure: standalone mode exits with status 2, and the command callback does not run.

## `optlyn.argument`

Import `argument` from the package root (`from `optlyn` import `argument``). Decorator that attaches a positional argument to the command being declared. It does not replace the function with a command; place it under `command` (or `group`) so the argument is attached before the command is built. The callback receives the value under the argument’s destination name.

### Signature

```
`argument`(*param_decls, **attrs)
```

- `param_decls` — positional declaration strings. A single destination name is the usual form. That name is the destination delivered to the callback. It is not an option flag: a single token that starts with `--` and then that destination name is a usage failure, not delivery of that destination.
- `attrs` — forwarded to the argument. Names used here include `required`, `nargs`, `envvar`, `default`, `type`, `deprecated`, `help`, and `metavar`.

Returns a decorator. That decorator attaches the argument and returns the same function (or, if the function is already a command, appends the argument to that command).

### Required, optional, and defaulted

A destination-only declaration (`required` omitted, no `default`) is required by default: omitting the position is a usage failure (standalone mode exits 2, callback not run). A message is written to standard error that identifies that argument’s destination. Case of that destination token is not pinned. Exact sentence wording is not pinned. The report names the omitted destination and does not name a sibling destination that was not omitted.

`required=False` may be omitted: the callback still runs. `required=True` on a variadic argument (`nargs=-1`) cannot be omitted: that is the same missing-required usage failure; supplying at least one token runs the callback with a non-empty sequence.

A declared `default` may be omitted: the callback still runs and receives that default. A supplied token overrides it.

An omitted optional argument with no `default`, a provided string, a declared default string, and an omitted variadic (empty sequence) are four distinguishable deliveries. The omitted-optional delivery is not a string and not a sequence. Exact absent encoding is not pinned.

Two unary arguments each receive one token as a scalar, in declaration order. Omitting the second required position is a usage failure. When the second is `required=False`, one token fills only the first and still succeeds.

### `nargs`

Omitting `nargs` is unary: one token, delivered as a scalar string (unless `type` or an integer `default` converts it). A unary value is not a one-element sequence.

`nargs=2` takes exactly two tokens and delivers them as an indexable pair (list or tuple), not as a joined string and not as a scalar. Supplying fewer tokens than that arity is a usage failure when the argument is required. `nargs=2` with `required=False`, or with a two-element `default`, may be omitted: the callback still runs.

`nargs=-1` is variadic (consume the rest). Tokens after a preceding unary argument go to the variadic destination as a sequence, in command-line order. With only the unary token present, the variadic destination is an empty sequence and the callback still runs. Variadic arity may be used at most once on a command. Declaring two consume-rest arguments is refused at declaration, or an invocation of that declaration does not succeed and does not run the callback.

### `--`

After a `--` token, subsequent tokens are arguments even if they look like options. A short-shaped token (one leading dash) and a long-shaped token (two leading dashes) are delivered as those strings. The `--` separator itself is not delivered as a value. Without that separator, those option-shaped tokens are a usage failure (standalone mode exits 2, callback not run), including when leftover undeclared tokens are allowed by `allow_extra_args`.

When `ignore_unknown_options` is true, option-shaped tokens may be consumed as declared arguments without a leading `--`, and the callback still runs. A leftover option-shaped token beyond declared arity is still a usage failure even then, unless leftover undeclared tokens are allowed by `allow_extra_args`.

### Extra tokens

Extra tokens beyond declared arity, when no variadic argument collects them and `allow_extra_args` is not true, are a usage failure (standalone mode exits 2, callback not run). When `allow_extra_args` is true, leftover undeclared tokens that are not option-shaped are not a usage failure: the callback still runs, and the declared argument still receives only the tokens that fill its arity.

### `envvar`

`envvar` is one environment name or a list of names. When the position is omitted, a non-empty value of that name fills the argument, including a required argument. An empty or absent variable does not supply a value: a required argument is then still missing, an optional argument stays omitted, and a declared `default` is used instead. When several names are listed, the first set (non-empty) name wins. `auto_envvar_prefix` does not invent argument names: a prefix-built key does not fill an argument, and neither does a key equal to the destination. A command-line token for the same argument wins over the environment.

A non-unary argument (fixed `nargs` of two, or variadic `nargs=-1`) splits a non-empty environment value into multiple tokens. A unary argument keeps the whole value as one scalar. A variadic argument typed `Path` splits on the platform path separator (see `Path`).

### `default` and `type`

A declared `default` is used when the position is omitted. A supplied token overrides it.

`type` converts the bound value. An integer `default` infers integer conversion when `type` is omitted, including when the value comes from `envvar`. An explicit `type=STRING` twin stays text. A constructible type such as `Path` is attached the same way (`type=Path()`).

### `deprecated`

`deprecated=True` still parses and runs the callback. Combining `deprecated=True` with `required=True` is refused at declaration. A destination-only declaration is required by default, so `deprecated=True` on that form is also refused at declaration. `required=False` or a declared `default` may be combined with `deprecated=True`. The deprecation warning appears only when the user actually supplied the argument; omitting a defaulted deprecated argument is indistinguishable from the otherwise identical non-deprecated twin after the shared default is delivered. Exact warning wording is not pinned.

### `help`

Author `help` text on this argument appears in a `Positional arguments` section on the `--help` page. When `help` is omitted, that author string is absent from the page.

### `metavar`

`metavar` is the placeholder for this argument on the usage line of the `--help` page. When omitted, the placeholder is the destination name in uppercase. An author string passed as `metavar` appears on that usage line.

That author string is this argument’s own placeholder. It is not the command’s options placeholder: the same word passed as `options_metavar` on `command` occupies a different place on the usage line than when it is this argument’s `metavar`.

## `optlyn.clear`

Import `clear` from the package root (`from `optlyn` import `clear``). Clears the visible terminal. When standard output is not a terminal, the call does nothing.

### Signature

```
`clear`()
```

No arguments. No return value is required.

### Observable behavior

When standard output is not a terminal, the call is a no-op: it does not write, and output that surrounds the call is indistinguishable from the same writes with the call omitted.

When standard output is a terminal, the call writes a screen-clear sequence. After surrounding payload text is removed, the remainder is distinguishable from a run that never called `clear`. Exact CSI opcodes are not pinned.

## `optlyn.command`

Import `command` from the package root (`from `optlyn` import `command``). Decorator that builds a command and uses the decorated function as the callback. The decorated name is then a command instance: it can be invoked as a command-line application, passed to a group’s `add_command`, and has `main`.

May be applied by calling `command` and then applying the result to a function. Keyword arguments such as `name`, `help`, and `context_settings` are accepted on that call. Parameters previously attached to the function by `option` or `argument` are registered on the created command.

### Signature

```
`command`(name=None, cls=None, **attrs)
```

- `name` (`str` or `None`). A string is the exported command name and overrides the default. `None` derives the name from the function.
- `cls` — command class to instantiate. `None` selects the default command class.
- `attrs` — forwarded to that class. Names used here include `help`, `context_settings`, `add_help_option`, `deprecated`, `hidden`, `options_metavar`, and `short_help`.

`help` is a string forwarded onto the command. An explicit `help` string is the command description on the help page. When it is supplied, a docstring is not required for that description to appear.

`context_settings` is a mapping forwarded onto the command. It carries invocation-context settings, including `allow_extra_args` and `ignore_unknown_options`. When `allow_extra_args` is true, leftover undeclared tokens that are not option-shaped are not a usage failure and the callback still runs with a successful standalone exit; the declared argument still receives only the tokens that fill its arity. When that flag is omitted or not true, leftover undeclared tokens are a usage failure (standalone mode exits 2, callback not run), unless a variadic `nargs=-1` argument collects them. An option-shaped token (a leading dash, with no preceding `--` separator) remains a usage failure even when `allow_extra_args` is true. When `ignore_unknown_options` is true, option-shaped tokens may be consumed as declared arguments without a leading `--` separator and the callback still runs. When that flag is omitted, those tokens are a usage failure (standalone mode exits 2, callback not run). A leftover option-shaped token beyond declared arity is still a usage failure even when `ignore_unknown_options` is true, unless leftover undeclared tokens are allowed by `allow_extra_args`.

Returns a command instance.

### `main`

```
`main`(`args`=None, `prog_name`=None, `standalone_mode`=True, **extra)
```

Program entry on the command instance.

- `args` — argument tokens after the program name. `None` (the default) uses `sys.argv[1:]`. A list of strings is the tokens to parse.
- `prog_name` — program name used in usage and help. `None` derives it from the process. A supplied string is the name that appears on the usage line.
- `standalone_mode` — default `True`. When `True`, a successful run (callback completed) exits 0; a usage failure exits 2 and does not run the callback.
- Extra keywords other than those named parameters are forwarded to the invocation context. Names used that way include `auto_envvar_prefix`.

`auto_envvar_prefix` is a string prefix for automatic environment names of options. It does not invent environment names for arguments: a prefix-built key does not fill an `argument`.

### Observable invocation

- A valid argument list runs the callback once. Output the callback writes to standard output is present.
- Unknown option tokens, missing required parameters, and leftover tokens that are not allowed are usage failures: status 2 in standalone mode, callback not run. A message is written to standard error. A missing required argument identifies that argument’s destination on standard error. Case of that destination token is not pinned.

### `add_help_option`

`add_help_option` is a boolean forwarded onto the command. When omitted, automatic help is enabled: `--help` prints the help page, exits 0, and does not run the command callback.

`add_help_option=False` disables that automatic option. Then `--help` is an unknown option: standalone mode exits 2, the callback is not run, and the command description page is not printed. `help_option("--help")` on that command restores successful help for `--help`.

### `deprecated`

`deprecated=True` still parses and runs the callback. A successful standalone run exits 0. A deprecation warning is distinguishable from ordinary callback output and from a usage failure. An unknown option on that same command is still a usage failure (standalone mode exits 2, callback not run).

`deprecated=False` is the non-deprecated twin.

An author string passed as `deprecated` is a custom note: that string appears in the warning remainder and does not appear on the otherwise identical non-deprecated twin.

`--help` on a deprecated command still prints a live help page, exits 0, and does not run the callback. After the exported name and the description are stripped, that page’s remainder is distinguishable from the otherwise identical non-deprecated twin. Exact warning wording and exact help-mark wording are not pinned.

### `hidden`

`hidden=True` omits this command from a parent group’s `--help` page: the exported name is absent. A visible sibling on that same parent is still listed. Complete mode also omits it: completing with an empty token lists a visible sibling and does not list the hidden name, and a prefix or full-token incomplete that matches the hidden name still omits it. The parent still accepts that name when fully typed and runs this command’s callback.

### `options_metavar`

`options_metavar` is the placeholder for options on this command’s usage line. An author string passed as `options_metavar` appears on that line as given: it is used as its own whitespace-separated token, not re-wrapped in extra brackets.

When omitted, a default options placeholder still occupies a place on the usage line after the program name and a required argument’s uppercase destination are stripped. That default placeholder is not this command’s argument metavar: the same word passed as `metavar` on a required `argument` occupies a different place on the usage line than when it is this command’s `options_metavar`.

### `short_help`

`short_help` is the one-line listing text for this command when it is shown as a child on a parent group’s `--help` page.

When omitted, that listing is the first sentence of the docstring. A later sentence does not appear. When that first sentence cannot fit on one line at the terminal width, it is ellipsized: a tail word that is present at a width that fits is absent at a narrower width.

An author string passed as `short_help` replaces that first-sentence listing. The author string appears next to the child name; the distinctive first-sentence word of the docstring does not.

## `optlyn.command.main.default_map`

Extra keyword on `main`. Extra keywords other than the named `main` parameters are forwarded to the invocation context. Names used that way include `default_map`.

```
`main`(`args`=None, `prog_name`=None, `standalone_mode`=True, **extra)
```

`default_map` is a mapping of parameter defaults that override declared defaults.

On a group, the map nests by child name, then by destination: the entry for a registered child is itself a mapping from that child’s `option` or `argument` destination to the mapped value. Invoking that child with the flag or position omitted uses the mapped value instead of the declared `default`. A nested entry whose outer key is a different child name does not fill this child. An empty inner mapping for this child does not fill a required option (standalone mode exits 2, callback not run).

On a leaf command invoked directly, the map is keyed by destination.

A command-line token for the same parameter beats the mapped value.

A string in the map is split the same way an environment value is split only when that parameter’s per-occurrence arity is not one. Default split is whitespace: an `option` with `nargs=2` receives the two pieces as an indexable pair. A `type=Path()` option with `nargs=2` splits on the platform path separator instead (a colon on Unix). A unary option keeps the whole string as one scalar. A sequence in the map is used as-is: it is not split.

A map string for a repeatable option (`multiple=True`) whose per-occurrence arity is one is not split and is a usage error that names that option’s public flag (standalone mode exits 2, callback not run). The same refusal applies to a declared non-sequence `default` on that repeatable option.

A mapped integer is delivered as that integer. A mapped value satisfies a required option when the flag is omitted. The same nested map fills an omitted `argument` under that destination.

## `optlyn.command.main.token_normalize_func`

Extra keyword on `main`. Extra keywords other than the named `main` parameters are forwarded to the invocation context. Names used that way include `token_normalize_func`.

```
`main`(`args`=None, `prog_name`=None, `standalone_mode`=True, **extra)
```

`token_normalize_func` is a function of one string that returns a string. It applies to option names, `Choice` values, and command names.

```
`token_normalize_func`(token)
```

A lowercase function makes an uppercased option name, choice value, or command name match the declared form, and the callback runs. An identity function (one that returns the token unchanged), or omitting the extra, leaves that uppercased token a usage failure (standalone mode exits 2, callback not run). A token that still does not match after the function is a usage failure.

## `optlyn.confirm`

Import `confirm` from the package root (`from `optlyn` import `confirm``). Standalone helper that asks a yes/no question and returns a boolean.

### Signature

```
`confirm`(text)
`confirm`(text, `abort=True`)
```

- `text` — the question shown to the user. A plain string is accepted. A value produced by `style` is also accepted.
- `abort` — when `abort=True`, a negative answer aborts the program. When omitted, both answers return a boolean and do not abort.

Returns a boolean.

### Observable behavior

Reads a line from standard input. The answer `yes` is true. The answer `no` is false.

When `abort` is omitted, a negative answer does not abort: the call returns false and the caller continues.

When `abort=True`, a negative answer is an abort: standalone mode exits with status 1, writes an abort indication on standard error that is distinguishable from a usage error, and does not run the remaining command work after the call. An affirmative answer returns true and the caller continues.

The author’s question text appears on standard output. Prompt punctuation, abort-sentence wording, and exception types are not pinned.

### Styled text

When the message is produced by `style`, ANSI styling is stripped from that message if the output stream is not a terminal, and kept if the stream is a terminal.

### End of file

End of file while asking is an abort: standalone mode exits with status 1, writes an abort indication on standard error that is distinguishable from a usage error, and does not run the remaining command work.

## `optlyn.confirmation_option`

Import `confirmation_option` from the package root (`from `optlyn` import `confirmation_option``). Decorator that attaches a boolean confirmation flag. Place it under `command` (or `group`) the same way as `option`.

### Signature

```
`confirmation_option`()
`confirmation_option`(*param_decls, **attrs)
```

- `param_decls` — option names. When omitted, the single name `--yes` is used.
- `attrs` — forwarded to the underlying option. Names used here include `prompt`. The flag is a boolean flag, is not delivered to the command callback, and prompts when omitted.

Returns a decorator. That decorator attaches the flag and returns the same function (or, if the function is already a command, appends the flag to that command).

### Observable behavior

- If the user passes the flag (`--yes` when using the default name, or the author-supplied name), the command callback runs without a question. Standard input is not read: an empty stream and a hanging negative answer are both ignored.
- If the user omits the flag, a yes/no question is asked. An author `prompt` string, when supplied, is that question. The answer `yes` runs the command callback. The answer `no` is an abort: standalone mode exits with status 1, an abort indication is written to standard error that is distinguishable from a usage error, and the command callback does not run.
- End of file while that question is asked is an abort: standalone mode exits with status 1, an abort indication is written to standard error that is distinguishable from a usage error, and the command callback does not run.
- When standalone program mode is disabled, a declined confirmation does not become an abort-class exit; the failure propagates to the caller.

Prompt punctuation and abort-sentence wording are not pinned.

## `optlyn.custom_version_option`

Import `custom_version_option` from the package root (`from `optlyn` import `custom_version_option``). Decorator that attaches an eager version flag whose printed identity is exactly the string returned by an author callback. Place it under `command` (or `group`) the same way as `option`.

### Signature

```
`custom_version_option`(callback, *param_decls, **attrs)
```

- `callback` — callable that receives the current `Context` and returns a `str`. That return value is the whole printed identity.
- `param_decls` — option names. When omitted, the single name `--version` is used.
- `attrs` — forwarded to the underlying option. The flag is eager, is not delivered to the command callback, and does not require other parameters.

Returns a decorator. That decorator attaches the flag and returns the same function (or, if the function is already a command, appends the flag to that command).

### Observable behavior

- Invoking `--version` prints the callback’s return value to standard output and exits 0. The command callback does not run, even when other required options are missing.
- The printed page is the callback string as-is: after that string is removed, only whitespace remains. The built-in package / program / version message used by `version_option` is not wrapped around the return value, and no other surrounding label is added. A ready-made `version_option` identity on the same program name is therefore a different stdout page.
- The callback is invoked with an instance of `Context` (the invocation context).
- The flag is eager. If both this flag and help appear on the command line, whichever eager flag the user typed first wins and exits.

## `optlyn.echo`

Import `echo` from the package root (`from `optlyn` import `echo``). Writes a message to standard output. When that message already contains ANSI styles, those styles are kept or stripped according to whether the stream is a terminal and according to the current invocation’s color flag.

### Signature

```
`echo`(message)
`echo`(message, nl=False)
`echo`(message, err=True)
```

- `message` — payload to write. A string returned by `style` is accepted, as is plain text, as are bytes.
- `nl` — trailing newline. When omitted, a trailing newline is appended after the payload on the destination stream. `nl=False` writes the payload without appending a newline: the written bytes equal the payload, not the payload plus a newline.
- `err` — destination stream. When omitted, the write goes to standard output. `err=True` writes to standard error instead: the payload appears on standard error and not on standard output.

When `nl` and `err` are omitted, the original payload characters appear on standard output with a trailing newline.

### Unicode and binary

A Unicode payload is written even when the stream encoding cannot represent it with ordinary printing. Bytes payloads are written as those bytes.

### Color flag on this thread

`echo` reads the invocation context that is current on this thread (the same context `get_current_context` returns) and inherits that invocation’s color flag. The top-level run accepts `color` as an extra keyword on `main` and forwards it onto that context.

- Force on (`color=True`): ANSI styles in the message are kept even when standard output is not a terminal, but only while this thread has entered that context. Sequences that wrapped the payload stay both before and after it.
- Autodetect (`color` omitted, or a null color flag): when standard output is not a terminal, ANSI styles are stripped and the payload text remains; when standard output is a terminal, styles are kept.
- Force off (`color=False`): ANSI styles are stripped even when standard output is a terminal. The payload text remains.

A thread that has not entered the invocation context does not inherit that flag. On such a thread, a styled message written to a non-terminal stream is stripped even if the parent invocation used `color=True`.

Plain text passed to `echo` is written without inventing styles. After the payload is removed, the remainder of a styled write is distinct from the remainder of a plain write of the same payload under the same force-on invocation.

## `optlyn.echo_via_pager`

Import `echo_via_pager` from the package root (`from `optlyn` import `echo_via_pager``). Writes long text through a pager when the session is interactive, and to standard output without launching a pager when it is not.

### Signature

```
`echo_via_pager`(text_or_generator)
```

- `text_or_generator` — a complete string, or an iterator (including a generator) of string chunks.

No return value is required. Pager color-flag spelling is not pinned.

### Interactive versus not

When the session is interactive, the text is fed to a pager. If the environment variable `PAGER` is set, that command is the pager that is launched, and the payload bytes are delivered to it.

When the session is not interactive, the text is written to standard output and `PAGER` is not launched.

### Strings, chunks, and flush

A complete string is written as that text. An iterator of chunks is written in order so every chunk’s text appears.

Chunked output is flushed as each chunk is written. A generator that yields a first chunk, then waits until that chunk has been observed by the pager, then yields a later chunk, is not held until it finishes: the first chunk is visible to the pager before the generator yields the next.

### Styles and process standard output

Styles are kept or stripped according to what the destination supports.

When the destination is not a terminal, ANSI styles in the text are stripped and the payload text remains.

When the destination supports styles, ANSI styles are kept. After the payload is removed, that remainder is distinguishable from an unstyled write of the same payload and from the stripped destination.

A pager that writes to the process standard output does not close that real stream. After `echo_via_pager` returns, a later `echo` of further text still appears on standard output.

## `optlyn.edit`

Import `edit` from the package root (`from `optlyn` import `edit``). Opens the user’s editor on a string or on a filename.

### Signature

```
`edit`(text, editor=...)
`edit`(filename=..., editor=...)
```

- `text` — the original string to edit, passed positionally.
- `editor` — the editor command to invoke. The command is given a filesystem path it can read and write.
- `filename` — when supplied, edit that path instead of a temporary copy of `text`.

### String form

The given `editor` command is invoked on a file that holds the original text.

If the editor writes new contents to that file, the call returns the saved text as a string, equal to what the editor wrote.

If the editor exits without saving, the call returns absent: the result is distinguishable from the saved text and from the unsaved original. The spelling of absent is not pinned.

### Filename form

When `filename` is supplied, the editor is invoked on that path. The file on disk receives what the editor writes. The call returns no text: the result is the same absent value as a string-form quit without saving, and is distinguishable from a string-form save.

## `optlyn.format_filename`

Import `format_filename` from the package root (`from `optlyn` import `format_filename``). Converts a filesystem name that may not be Unicode into text that can be printed without failing. The call does not require an active command invocation.

### Signature

```
`format_filename`(filename)
```

- `filename` — a filesystem name as text, including a name that is not valid Unicode.

Returns a Python `str`. The call does not fail.

A name that is already printable Unicode remains printable: distinctive characters from that name appear in the result.

A name that is not valid Unicode still returns a `str`. That result can be written through a UTF-8 encoder in strict error mode without failing. Two different illegal names remain distinguishable from each other.

The exact replacement characters used for undecodable parts are not pinned.

## `optlyn.formatting`

The module `optlyn.formatting` is imported as `from `optlyn.formatting` import …`. Importing it performs no I/O, starts no processes, and opens no sockets.

These names are importable as ``optlyn.formatting`.<name>` and as `from `optlyn.formatting` import <name>`:

- `wrap_text`

## `optlyn.formatting.wrap_text`

Import `wrap_text` from `optlyn.formatting` (`from `optlyn.formatting` import `wrap_text``). Helper exported by that submodule. It is not imported from the package root.

### Signature

```
`wrap_text`(text)
```

- `text` — a string. A short ASCII string is accepted.

The call does not fail. Return shape is not pinned.

## `optlyn.get_app_dir`

Import `get_app_dir` from the package root (`from `optlyn` import `get_app_dir``). Returns the per-user application config directory for a given application name.

### Signature

```
`get_app_dir`(app_name)
`get_app_dir`(app_name, force_posix=True)
```

- `app_name` — the application name, as text. It may contain spaces and mixed case.
- `force_posix` — when `force_posix=True`, POSIX systems use a dotted name in the home directory instead of the platform config location. When omitted, the platform location is used.

Returns a filesystem path as a string.

### Unix folder name

On Unix the directory name under the config location is the application name with whitespace runs turned into a single dash and letters lowercased. For the application name `Foo Bar` that folder name is `foo-bar`. The original mixed-case spaced name does not appear in the path.

### Unix paths

When `XDG_CONFIG_HOME` is unset, the path is the user’s home directory, then `.config`, then that folder name.

When `XDG_CONFIG_HOME` is set, the path is that directory joined with the folder name, not the home `.config` location.

### POSIX-forced mode

With `force_posix=True` on a POSIX system, the path is the user’s home directory joined with a leading-dot folder name (dot plus the same dashed lowercase name), even when `XDG_CONFIG_HOME` is set. That path is distinct from the XDG path for the same application.

### Other platforms

The lookup follows the process platform identifier. When that identifier is `darwin`, without POSIX-forced mode, the path is the home directory joined with `Library`, then `Application Support`, then the application name as given (spaces and case preserved). For `Foo Bar` that is `~/Library/Application Support/Foo Bar`. The Unix dashed folder name does not appear as the last path component.

When that identifier is `win32`, the path is the roaming application-data folder (`APPDATA`) or the local application-data folder (`LOCALAPPDATA`) joined with the application name as given. The Unix dashed folder name does not appear as the last path component.

## `optlyn.get_current_context`

Import `get_current_context` from the package root (`from `optlyn` import `get_current_context``). Returns the invocation context that is active on the calling thread.

### Signature

```
`get_current_context`()
```

Returns the current invocation context. That object exposes `obj`, the author object stored on the context.

During a command callback on the thread that is running the invocation, the call succeeds. `obj` on the returned context is the author object that callback’s context holds, including a value assigned on that context earlier in the same callback.

The current context is thread-local. Another thread does not see it unless that context is entered there. Entering the context as a context manager (`with ctx`) makes `get_current_context` return that context on the entering thread for the duration of the block, and `obj` on the returned context is that same author object.

On a thread that has never entered the context, the call does not return the other thread’s context or that context’s `obj`. `echo` on such a thread also does not inherit that invocation’s color flag.

## `optlyn.get_pager_file`

Import `get_pager_file` from the package root (`from `optlyn` import `get_pager_file``). Context manager that yields a writable pager stream.

### Signature

```
`get_pager_file`()
```

No arguments. Usable as `with `get_pager_file`() as pager`.

The yielded `pager` is a writable text stream. It accepts `write` of string chunks and `flush`. Leaving the `with` block finishes the pager.

Pager color-flag spelling is not pinned.

### Interactive versus not

When the session is interactive, the stream launches a pager. If the environment variable `PAGER` is set, that command is the pager that is launched, and text written to the stream (and flushed) is delivered to it.

When the session is not interactive, text written to the stream goes to standard output and `PAGER` is not launched. Chunks written before the block exits appear in that output.

### Process standard output

A pager that writes to the process standard output does not close that real stream. After the `with` block ends, a later `echo` of further text still appears on standard output.

## `optlyn.getchar`

Import `getchar` from the package root (`from `optlyn` import `getchar``). Reads one character from the terminal.

### Signature

```
`getchar`()
```

No arguments. Returns the character as a string.

### Observable behavior

The character is read from the terminal even when standard input is a pipe. Bytes waiting on the piped standard input are not consumed as the character.

### Interrupt and end-of-file

An interrupt key sequence and an end-of-file key sequence are failures, not returned as those raw characters. The two failures are distinguishable from each other. Exception types are not pinned.

## `optlyn.group`

Import `group` from the package root (`from `optlyn` import `group``). Decorator that builds a group and uses the decorated function as the callback. A group is a command that holds named subcommands. The decorated name is then a group instance: it can be invoked the same way as a command (including `main`), and it exposes `add_command`.

May be applied as `group`() with parentheses and no arguments. Name derivation and attachment of decorated `option` / `argument` parameters are the same as `command`.

### Signature

```
`group`(name=None, cls=None, **attrs)
```

- `name` (`str` or `None`) — same rules as `command`.
- `cls` — group class to instantiate. `None` selects the default group class.
- `attrs` — forwarded to that class. Names used here include `chain`, `invoke_without_command`, `sources`, `context_settings`, `epilog`, and `hidden`.

Returns a group instance.

An `argument` declared on the group is delivered to the group callback under that destination. Invoking the group with the positional token and then a registered child name runs the group callback with that positional value and dispatches the child.

`chain` is a boolean forwarded onto the group. When `True`, this group is a chaining group. When `chain=True` and standalone mode is off, the invocation itself returns that same positional sequence of the dispatched children’s return values in command-line order, even when no `result_callback` is registered. Swapping the child names on the command line swaps the positions in that returned sequence. The Python type of the sequence is not pinned. That return is not this group’s own callback return. A standalone run of the same chain exits 0.

`invoke_without_command` is a boolean forwarded onto the group. When omitted or not true, a run with no extra arguments does not run the group callback. When true, a run with no extra arguments runs the group callback and no child; a named child still runs the group callback first, then the child.

`sources` is a list of groups forwarded onto the group class. Pass it together with `cls` set to `CommandCollection`:

```
`group`(cls=`CommandCollection`, `sources`=[…])
```

Each entry is a group that already has children registered on it. The constructed collection’s listing and lookup are the union of those sources’ children. A name that exists on any source is accepted as the next token and runs that source child’s callback; a child of a different name on another source does not run. Changing which groups are passed as `sources` changes which names are listed on help and which names dispatch. An empty extra-argument list is this collection’s missing-subcommand help (this collection’s description, not a source group’s).

### `context_settings`

`context_settings` is a mapping forwarded onto the group the same way `command` forwards it onto a command. Names used here include `allow_interspersed_args` and `default_map`.

```
`group`(`context_settings`={`allow_interspersed_args`: True})
`group`(`context_settings`={`default_map`: ...})
```

When `allow_interspersed_args` is omitted or not true, the subcommand name ends this group’s own option parsing: a group option after that child name is not delivered to the group callback. When `allow_interspersed_args` is true, a group option after the child name is still parsed for this group: the group callback receives that value and the named child still runs.

`default_map` on this mapping nests by child name, then by destination: the entry for a registered child is itself a mapping from that child’s `option` or `argument` destination to the mapped value. Invoking the named child with the flag omitted uses the mapped value instead of the declared `default`. A nested entry for a different child name does not fill this child.

### `epilog`

`epilog` is a string forwarded onto the group. When set, that string appears on the group’s `--help` page at the end: the group description, the group’s option help, positional-argument help, and listed child names all appear before it.

### `hidden`

`hidden=True` omits this group from a parent group’s `--help` page: the exported name is absent. A visible sibling group on that same parent is still listed. The parent still accepts that name when fully typed: invoking the hidden name and then a registered child of this group runs this group’s callback and then that child.

### `add_command`

```
`add_command`(cmd, name=None)
```

Registers another command on this group.

- `cmd` — the command (or nested group) to attach.
- `name` (`str` or `None`) — exported name under which the parent accepts the child. When omitted, the child’s own name is used.

The parent accepts the registered name as the next token and runs that child’s callback. Invoking a named child also runs this group’s callback.

## `optlyn.group.context_settings.default_map`

Authors set `default_map` as a key of a `context_settings` mapping passed to `group`. `context_settings` is a mapping forwarded onto the group the same way `command` forwards it onto a command.

```
`group`(`context_settings`={`default_map`: ...})
```

That nested `default_map` is keyed by child name, then by destination: the entry for a registered child is itself a mapping from that child’s `option` or `argument` destination to the mapped value. Invoking the named child with the flag omitted uses the mapped value instead of the declared `default`. A nested entry for a different child name does not fill this child.

## `optlyn.help_option`

Import `help_option` from the package root (`from `optlyn` import `help_option``). Decorator that attaches an extra eager help flag. Place it under `command` (or `group`) the same way as `option`.

### Signature

```
`help_option`(*param_decls, **attrs)
```

- `param_decls` — option names for this extra help flag. `help_option("--help")` declares the conventional name `--help`.

Returns a decorator. That decorator attaches the flag and returns the same function (or, if the function is already a command, appends the flag to that command).

### Observable behavior

- Invoking a declared name prints the help page, exits 0, and does not run the command callback. The page is the same successful help page as the automatic `--help` flag.
- Declaring an extra name does not remove the automatic help option. When automatic help is still enabled, both the extra name and `--help` print help and exit 0.
- When the command is declared with `add_help_option=False`, `--help` is an unknown option unless the author declared it. `help_option("--help")` on that command restores successful help for `--help`.

## `optlyn.launch`

Import `launch` from the package root (`from `optlyn` import `launch``). Opens a URL or filename with the default associated application, and can open a file manager with the file selected.

### Signature

```
`launch`(url, wait=True)
`launch`(url, wait=True, locate=True)
```

- `url` — a URL or a filesystem path, passed positionally.
- `wait` — `wait=True` waits until the launched program has been given the URL or path.
- `locate` — `locate=True` opens a file manager with the file selected instead of opening the file with the default associated application.

### Default application

With `wait=True` and `locate` omitted, the default associated application is launched and receives the URL or the filename. That value appears in the launched program’s argument list.

### File-manager select

With `wait=True` and `locate=True`, a file manager is launched with the file selected. After the filename is removed from the launched argument text, the remainder is distinguishable from opening the same path with the default associated application.

Opener executable names are not pinned.

## `optlyn.make_pass_decorator`

Import `make_pass_decorator` from the package root (`from `optlyn` import `make_pass_decorator``). Builds a decorator that injects an author object of a given type as the callback’s first argument.

### Signature

```
`make_pass_decorator`(object_type)
`make_pass_decorator`(object_type, ensure=True)
```

- `object_type` — a type. The decorator looks for an instance of this type on the current context and its parents.
- `ensure` — when omitted, treated as false. `ensure=True` constructs an empty instance if none is found.

Returns a decorator. That decorator is applied to the author callback the same way as `pass_context`: call it on the function, then pass the result to `group` or `command` (or use it as a decorator).

When the command or group runs, the wrapper calls the author function with the found (or created) object in the first position, then the declared parameter values.

### Lookup on the parent chain

The search walks the current context, then each parent. The closest instance of `object_type` is the one injected. A nearer context whose `obj` is a different type does not hide a matching instance further up the parent chain.

If a match is found, that same instance is injected. `ensure=True` does not replace it with a new empty instance.

### `ensure=True` when absent

If no instance of `object_type` is on the chain and `ensure=True`, the type is called with no arguments. That new instance is what the callback receives. Fields left at their constructor defaults stay at those defaults. The new instance is not an instance of a different type already stored on a parent.

### Without `ensure`

If no instance of `object_type` is on the chain and `ensure` was omitted or false, no empty instance of that type is created and the callback does not receive one.

## `optlyn.open_file`

Import `open_file` from the package root (`from `optlyn` import `open_file``). Opens a file or a standard stream by the same dash rule as `File`. Usable as a context manager (`with `open_file`(...) as handle`). The call does not require an active command invocation.

### Signature

```
`open_file`(filename, "r")
`open_file`(filename, "w")
`open_file`(filename, "w", `lazy=True`)
`open_file`(filename, "w", `lazy=False`)
`open_file`(filename, "w", `atomic=True`)
```

- `filename` — a filesystem path as text (relative or absolute), or the token `-`.
- The second argument is the open mode: `r` reads text; `w` writes text.

Keyword arguments:

- `lazy` — `lazy=True` delays opening until first I/O. `lazy=False`, and omitting the argument, opens immediately.
- `atomic` — `atomic=True` writes to a sibling temporary file and replaces the target when the handle is closed. Temporary names are not pinned.

Returns an open file. That object can be read, written, flushed, and used as a context manager according to the mode.

### Dash token

`-` with `r` reads standard input. `-` with `w` writes standard output. Leaving the caller’s `with` block does not close those process streams: standard input remains open (`closed` is false) and any unread remainder is still readable; further writes to standard output still appear.

### Real files

A real path is opened as a file. Leaving the `with` block closes that file: the handle reports closed, or a further write fails. Contents written through the handle are stored on that path.

### Lazy and atomic write

`lazy=True` on a write does not truncate the path if the handle is never used. The original contents remain. Writing through the handle then stores what was written.

`lazy=False` on a write, and omitting `lazy`, opens immediately. Even if the handle is never used, the original contents are not preserved.

`atomic=True` on a write: after a write and a flush, an independent reader of the original path still sees the original contents. After the `with` block ends, the original path holds the written contents.

## `optlyn.option`

Import `option` from the package root (`from `optlyn` import `option``). Decorator that attaches a named option to the command being declared. It does not replace the function with a command; place it under `command` (or `group`) so the option is attached before the command is built. The callback receives the converted value under the option’s destination name.

Several options may be attached to one command. Each has its own public flag and destination; conversion and delivery for one do not fill a sibling destination.

### Signature

```
`option`(*param_decls, **attrs)
```

- `param_decls` — positional declaration strings. A name with two leading dashes is a long option. A declared name with no leading dash is the destination delivered to the callback. Several names (a public flag and a destination) may be given; they all set the same destination.
- `attrs` — forwarded to the option. Names used here include `is_flag`, `type`, `default`, `help`, `multiple`, `envvar`, `allow_from_autoenv`, `nargs`, `prompt`, `required`, `prompt_required`, `hide_input`, `confirmation_prompt`, `deprecated`, `metavar`, `shell_complete`, `hidden`, `expose_value`, `flag_value`, `is_eager`, `show_default`, and `show_envvar`.

Returns a decorator. That decorator attaches the option and returns the same function (or, if the function is already a command, appends the option to that command).

### Optional flags

An option is optional unless the author marks it `required=True`. Omitting that flag is a usage failure: standalone mode exits 2, and the command callback does not run. A prefix-built environment value and a nested default-map entry still fill that form when the flag is omitted, as already written under `allow_from_autoenv` and on the default-map page.

`is_flag=True`: the flag is present alone, with no following token. When the flag is omitted, the callback receives false. When the flag is present before a `--` separator, the callback receives true.

After a `--` token, a token that matches that flag’s public name is an argument, not the flag: the flag destination stays false and the following positional receives that token.

Boolean conversion is used automatically for such a flag: the author does not attach `type=BOOL`. Presence delivers true; omission delivers false.

### `type`

`type` converts the token bound to this option. Built-in types are attached as `type=INT`, `type=FLOAT`, `type=STRING`, `type=BOOL`, and `type=UUID`. Constructible types are attached the same way: an instance of `DateTime`, `Tuple`, `Choice`, `IntRange`, or `FloatRange`. A `ParamType` subclass instance and a conversion function are also accepted as `type`.

When `type` is omitted and no convertible `default` is set, the bound token is Unicode text.

An explicit `type=STRING` twin keeps a numeric-looking or boolean-looking token as text.

A `Tuple` type on an option sets that option’s arity to the inner-type length: `type=Tuple([INT, FLOAT])` consumes two tokens after the flag and delivers an indexable pair.

Conversion failure is a usage error that identifies this option’s public flag: standalone mode exits with status 2, a message on standard error names that public flag and does not name a sibling option that did not fail, and the command callback does not run. A sibling that converted successfully is not delivered. Exact wording is not pinned.

### `default`

A declared `default` is used when the option is omitted. A supplied token overrides it.

When the author does not set `type`, an integer `default` infers integer conversion, a float `default` infers float conversion, and a boolean `default` infers boolean conversion: a supplied token is converted as that type. A UUID object as `default` does not infer `UUID` conversion: a UUID-text token is delivered as text unless `type=UUID` is attached.

A default that is already the converted type is delivered unchanged when the option is omitted (it is not converted as a string).

### `envvar`

`envvar` names one environment variable, or a list of names. When the flag is omitted, a non-empty value of that name fills the option, including when the author marked the option required. The bound string is converted with this option’s `type`. A command-line token for the same option wins over that environment value.

When several names are listed, the first set (non-empty) name wins. An empty or absent variable does not supply a value: a declared `default` is used instead.

### `allow_from_autoenv`

When the invocation is given `auto_envvar_prefix`, each option may be filled from a variable built from that prefix, then each nested command name, then the option’s destination, all uppercased and joined by underscores, with dashes in every part turned into underscores. The top-level program name is not a part. A dashed prefix is normalized the same way. That prefix-built name fills an omitted option. It does not fill a sibling `argument`.

`allow_from_autoenv=False` opts this option out of that automatic prefix: the prefix-built name does not fill the option unless the author also declared that same name as `envvar`. An opted-out option whose `envvar` is a different name is filled from that declared name, not from the prefix-built name. When the author does not opt out, the prefix-built value still fills the option.

A command-line token wins over the prefix environment. A prefix-built value satisfies a required option when the flag is omitted: the environment string is converted with this option’s `type`. When that prefix-built name is absent, a required option is still missing (standalone mode exits 2, callback not run).

### `nargs`

`nargs` is the number of value tokens consumed per occurrence. Omitting it is unary: one token, delivered as a scalar.

`nargs=2` takes exactly two following tokens and delivers them as an indexable pair, not as a joined string and not as a scalar. It is not “consume the rest”: a leftover token after that pair is left for a following argument. Supplying the flag with fewer tokens than that arity is a usage failure: standalone mode exits 2, and the command callback does not run.

A string from the default map, or a non-empty `envvar` value, is split the same way only when this arity is not one. Default split is whitespace. A `type=Path()` option with `nargs=2` splits on the platform path separator instead (a colon on Unix). A unary option keeps the whole string as one scalar. A sequence in the default map is used as-is.

Combined with `multiple=True`, each occurrence still takes that many tokens, and the callback receives a sequence of those pairs. A default-map string for a repeatable option whose per-occurrence arity is one is not split and is a usage error that names that option’s public flag (standalone mode exits 2, callback not run). The same refusal applies to a declared non-sequence `default` on that repeatable option.

### `multiple`

`multiple=True` makes the option repeatable. The option may be given several times; the command callback receives the sequence of converted values in command-line order.

A declared `default` for a repeatable option is a sequence of values, delivered when the option is omitted, in that sequence’s order.

### `prompt`

`prompt` here is an option attribute, not a standalone helper of the same name. `prompt=True` asks when the option is omitted and converts the typed line. Command-line supply skips the prompt: a value given with an equals form or as a following token is delivered, and a waiting unused line is not consumed as the value.

`prompt=False` does not read a line: a declared `default` is delivered, and a waiting unused line is not consumed as the value.

A non-empty `envvar` value fills the option and skips the prompt: that environment value is delivered, and a waiting unused line is not consumed.

An author string passed as `prompt` replaces the name-derived prompt. The author string appears; the distinctive name-derived prompt text does not. Prompt punctuation is not pinned.

A declared `default`, including a callable that returns the value, still prompts: that default is shown in the prompt. A typed line is converted and delivered. An empty-line answer delivers the shown default. A callable default is invoked during that prompt, including on an empty-line answer. End of file with no line is an abort: standalone mode exits with status 1, an abort indication is written to standard error that is distinguishable from a usage error, and the command callback does not run. It is not delivery of the default. Command-line supply still skips the prompt, and the shown default does not appear.

A default-map value still prompts the same way: it is shown and used on an empty-line answer in place of a declared default.

Conversion failure at the prompt does not finish the invocation as a usage error. The option asks again until a valid line is given. The first valid line is the result; later lines are not consumed as a second answer. End of file before a valid value is that same abort class.

A `required=True` prompted option still asks when omitted (it is not a missing-option usage failure) and still skips when a value is given on the command line. End of file at that prompt is the abort class, distinguishable from omitting a non-prompting required option.

The origin that supplied the converted value is distinguishable: a command-line token, an `envvar` (or prefix-built) environment value, a default-map value, a declared `default`, and a line read because `prompt=True` are five different origins even when the converted value is the same. Exact origin spellings are not pinned.

### `prompt_required`

`prompt_required=False`, used with `prompt=True`, does not prompt when the option is fully omitted: the declared `default` is delivered even when standard input is empty, and a waiting unused line is not consumed as the value. The option still asks when the flag is present without a value. Combining `prompt_required=False` with `required=True` still prompts both when the option is omitted and when the flag is present without a value.

### `hide_input`

`hide_input` applies when this option prompts. `hide_input=True` hides typed input: the typed value is not echoed. When omitted or false, a visible prompt echoes the typed line. Both still deliver the typed value to the callback. When the command is invoked through `CliRunner`, a hidden prompt leaves the secret absent from captured `output`; a visible prompt includes it.

### `confirmation_prompt`

`confirmation_prompt=True` on `option`, used with `prompt=True`, asks twice. A matching pair is accepted and delivered to the callback. A mismatched pair is rejected and the pair of questions is asked again; the first mismatched values are not delivered. End of file after only one line, or after a mismatch with no matching pair, is an abort: standalone mode exits with status 1, an abort indication is written to standard error that is distinguishable from a usage error, and the command callback does not run. This is an `option` attribute, not only a behavior of `password_option`. Prompt punctuation is not pinned.

### `deprecated`

`deprecated=True` still parses and runs the callback. A deprecation warning is distinguishable from ordinary callback output and from a usage failure only when the user actually supplied that option, not when the value came only from a `default`. Omitting a defaulted deprecated option is indistinguishable from the otherwise identical non-deprecated twin after the shared default is delivered. Combining `deprecated=True` with `required=True` is refused at declaration. Combining `deprecated=True` with `prompt=True` is refused at declaration. Exact warning wording is not pinned.

### `help`

Author `help` text appears in that option’s record on the `--help` page, next to the option’s public name. After the public name and that help string are removed from the record, type-driven details remain (a `Choice` lists its allowed values; an otherwise identical `type=STRING` twin does not).

### `hidden`

`hidden=True` omits the option from the `--help` page: the declared public name is absent. Complete mode also omits it. Completing after a dash lists a visible sibling flag and `--help`, and does not list the hidden flag. A prefix or full-token incomplete that matches the hidden flag still omits it. The command line still accepts that name when fully typed and delivers the value to the callback.

### `metavar`

`metavar` is the placeholder for this option’s value on the `--help` page. An author string passed as `metavar` appears in that option’s help record, replacing the type-name placeholder.

When `metavar` is omitted, a value option’s default placeholder is the type name in uppercase, not the option’s destination name. Same-type value options share a remainder after the public name and help string are stripped; an `INT` remainder and a `STRING` remainder differ. A `Choice` type supplies its own placeholder: that remainder is distinguishable from an otherwise identical `type=STRING` twin and from a `type=INT` twin. Exact placeholder punctuation is not pinned.

A flag (`is_flag=True`) has no metavar: after the public name and help string are stripped, that remainder is emptier than a value option’s remainder. A counting option (`count=True`) likewise has no metavar.

The author string is also readable on the parameter object as `metavar`. An author `shell_complete` function receives that parameter and can read `param`.`metavar`. Two options that share one completer but declare different `metavar` strings are distinguishable through that attribute. When `metavar` is omitted, that attribute is empty: a reader treats it as missing.

### `shell_complete`

`shell_complete` is an author function used for this option’s suggestions in complete mode, instead of the option’s type completer.

```
`shell_complete`(`ctx`, `param`, incomplete)
```

- `ctx` — the invocation context for this run. Already-converted values of options parsed before this token are readable on that context under their destination names (`params`).
- `param` — this option. Its `metavar` is readable.
- `incomplete` — the incomplete token, possibly empty.

The function returns a sequence of suggestion strings, or of objects that expose a `value` attribute and may expose `help`. Complete mode writes those suggestions and does not run the command callback.

The same function attached to two options is distinguishable: each call sees that option’s own `param` (including a different `metavar`). A different incomplete token, or a different already-filled context value, produces a different suggestion stream. An empty incomplete token still yields a non-empty stream when the function returns a suggestion.

When a suggestion object carries `help`, zsh and fish complete streams are distinguishable from an otherwise identical stream without that help after the values are stripped, and swapping which value carries which help string is distinguishable the same way. bash and powershell still suggest the value without requiring that help string to appear.

When `shell_complete` is omitted, the attached `type` supplies suggestions. A custom `ParamType` that implements `shell_complete` is distinguishable from a `type=STRING` sibling. A `Choice` lists allowed values that match the incomplete prefix (an empty incomplete token lists every allowed value). A `File` or `Path` type carries the incomplete token rather than listing directory entries. An unmatched prefix yields empty suggestions, not a usage error.

### `expose_value`

`expose_value=False` hides this option from the command callback: the converted value is not passed as a function argument. The option is still parsed. A token that matches that public name is accepted and is not an unknown option; an undeclared sibling flag is still a usage failure (standalone mode exits 2, callback not run).

### `flag_value`

`flag_value` is the value delivered when this flag is present. Several options may share one destination as a feature-switch group: the callback receives the `flag_value` of the winning flag.

When those siblings are omitted, an explicit declared `default` beats a bare boolean flag’s auto-derived false. If still tied, the last declared option wins.

With `is_flag=False`, the flag may take an optional value: the flag alone yields the author’s `flag_value`; the flag plus a token (equals form or a following token) yields that token; omitting the flag entirely yields the declared `default`. A value option without this form, given the flag and no token, is a missing-value usage failure; the optional-value form is not.

When the flag has a non-boolean `flag_value` and `envvar` is set, a variable whose text equals that flag-value activates, and so does a recognized true token such as `true`. A recognized false token such as `false` deactivates: the delivered value is neither that flag-value nor the declared `default`. An unrecognized non-empty string, or an empty value, is treated as unset: the declared `default` is used, and it is not a usage error.

Within a feature-switch group, the option whose source is most explicit wins: a command-line token beats an `envvar` value, which beats a default-map value, which beats a declared `default`.

### `is_eager`

`is_eager=True` processes this option before missing required siblings are enforced. Combined with `expose_value=False`, an author `callback` on this option may finish the invocation when the flag is present: standalone mode exits 0, output that function wrote is present, and the command callback does not run, even when a required non-eager sibling is omitted. When the eager flag is omitted, that missing required sibling is still a usage failure (standalone mode exits 2, command callback not run, and that finishing output is absent).

### `show_default`

`show_default=True` shows this option’s declared `default` on the `--help` page, in that option’s record. When omitted or false, that default value is absent from the record after the public name and help string are stripped.

An author string passed as `show_default` replaces the raw default: that string appears in the record and the raw default does not.

For a boolean flag (`is_flag=True`) whose declared default is off (false), that default stays hidden even when `show_default=True`: the remainder matches the twin with the switch off. A boolean flag whose declared default is on (true) is revealed when the switch is on: that remainder differs from the twin with the switch off.

The same switch may be enabled for the whole invocation through the context: an invocation given `show_default` as true shows the declared default on an option that did not set the per-parameter switch.

### `show_envvar`

`show_envvar=True` shows this option’s declared `envvar` name on the `--help` page, in that option’s record. `show_envvar=False` omits that name. After the public name and help string are stripped, the two remainders differ.

## `optlyn.pass_context`

Import `pass_context` from the package root (`from `optlyn` import `pass_context``). Decorator that marks a command or group callback as wanting the current invocation context as its first argument.

### Signature

```
`pass_context`(f)
```

- `f` — the author callback. Its first parameter receives the invocation context. Remaining parameters are the converted values for parameters declared on that command or group.

Returns a wrapper. That wrapper is the callable `group` or `command` then uses as the callback. May be applied as @`pass_context`, or by calling `pass_context` on the function and passing the result to `group` (or `command`).

When the command or group runs, the wrapper calls `f` with the current invocation context in the first position, then the declared parameter values.

### `obj`

The injected context exposes `obj` as a writable author object. An assignment on a parent is visible to children unless a child replaces it. A descendant that reads `obj` sees the nearest replacement on the path, or the parent value when no child replaced it.

### `invoked_subcommand`

The injected context exposes `invoked_subcommand` so a group callback can tell a group-only run from a group-then-child run.

- `None` — no child is about to run (a group declared with `invoke_without_command=True` and invoked with no extra arguments).
- not `None` — a named child is about to run after this group callback.

On a non-chaining group, that non-`None` value is the exported name of the child that is about to run. Different child names yield different values.

On a chaining group (`chain=True`), the value when children are about to run is distinguishable from any one child’s exported name and from the no-subcommand value. Exact sentinel spelling is not pinned.

The group callback still runs before that child when a name is dispatched.

### `get_parameter_source`

The injected context exposes `get_parameter_source` so a callback can ask which source supplied a named parameter.

```
`get_parameter_source`(name)
```

- For a declared destination, the result identifies the origin that supplied that parameter. The distinguishable origins are prompt, command line, environment, default map, and declared default. The same converted value from two different origins yields two different results. Exact spellings of those results are not pinned.
- For a name that was not declared on the command, the result is `None`. An extra key stuffed through the default map or through `invoke` is not converted and is not a tracked source.

### `with_resource`

```
`with_resource`(resource)
```

Registers a resource on the injected context. The resource stays open through child commands and is closed when the invocation ends, including after a child usage failure and after process exit in standalone mode.

### `invoke`

```
`invoke`(cmd, **values)
```

Runs another command from inside a callback. Destination keywords supplied on the call are the values the target receives; the current command’s own parsed values are not substituted. An author object assigned on the current context is visible to the target. An extra keyword that is not a declared destination on the target is stuffed unconverted and is not a tracked source (`get_parameter_source` of that name is `None`).

### `forward`

```
`forward`(cmd)
```

Runs another command from inside a callback, filling the target from this command’s current parameter values. An author object assigned on the current context is visible to the target.

### Context manager

The injected context is a context manager. Entering it on another thread applies this invocation on that thread: `echo` inherits this invocation’s color force, and the author object on this context is visible there. Without entering, the other thread does not see this invocation.

### `exit`

```
`exit`()
`exit`(status)
```

Author clean stop from inside a callback that received this injected context. Work after the call does not run.

- With no argument, standalone mode is a process exit with status 0, not a remapped captured exception.
- With a supplied integer, standalone mode is a process exit with that status. A supplied `1` is still that process exit, not a remapped captured exception.
- When standalone mode is off, the call does not raise and does not exit the process. Work after the call still does not run.

### `abort`

```
`abort`()
```

Author abort from inside a callback that received this injected context. Work after the call does not run.

- In standalone mode this is abort-class process exit with status 1, not a remapped captured exception. Standard error carries an abort indication that is distinguishable from a usage-error report. Exact wording is not pinned.
- When standalone mode is off, the abort still propagates to the caller.

## `optlyn.pass_obj`

Import `pass_obj` from the package root (`from `optlyn` import `pass_obj``). Decorator that marks a command or group callback as wanting the current context’s author object as its first argument.

### Signature

```
`pass_obj`(f)
```

- `f` — the author callback. Its first parameter receives the author object stored on the current invocation context (`obj`). Remaining parameters are the converted values for parameters declared on that command or group.

Returns a wrapper. That wrapper is the callable `group` or `command` then uses as the callback. May be applied as @`pass_obj`, or by calling `pass_obj` on the function and passing the result to `group` (or `command`).

When the command or group runs, the wrapper calls `f` with the current context’s `obj` in the first position, then the declared parameter values.

A child sees the parent’s author object unless a callback on the path assigned a replacement to `obj`. The replacement is what a descendant decorated with `pass_obj` receives. If no callback on the path replaced it, the descendant receives the ancestor’s object.

This is the current context’s `obj`, not a search for a given type. A nearer replacement hides the ancestor’s object from `pass_obj`.

The injected value is that same object instance. A later sibling decorated with `pass_obj` sees mutations made through an earlier sibling’s injected object.

An author object assigned on the current context is visible to a target invoked or forwarded from that callback when the target is decorated with `pass_obj`.

## `optlyn.password_option`

Import `password_option` from the package root (`from `optlyn` import `password_option``). Decorator that attaches a password option: prompt, hidden input, and confirmation. Place it under `command` (or `group`) the same way as `option`.

### Signature

```
`password_option`(*param_decls, **attrs)
```

- `param_decls` — option names and an optional destination, with the same rules as `option`.
- `attrs` — forwarded to the underlying option. Prompting, hidden input, and a confirmation prompt are enabled.

Returns a decorator. That decorator attaches the option and returns the same function (or, if the function is already a command, appends the option to that command). The callback receives the typed secret under the option’s destination name.

### Observable behavior

When the option is omitted from the command line, the user is asked for a value and then asked again. Hidden input does not echo the typed value.

A matching pair is accepted and delivered to the callback. A mismatched pair is rejected and the pair of questions is asked again; the first mismatched values are not delivered.

End of file after only one line, or after a mismatch with no matching pair, is an abort: standalone mode exits with status 1, an abort indication is written to standard error that is distinguishable from a usage error, and the command callback does not run.

When the command is invoked through `CliRunner`, the secret does not appear in the captured `output`.

## `optlyn.pause`

Import `pause` from the package root (`from `optlyn` import `pause``). Prints a short message and waits for a key when interactive; when not interactive, does nothing.

### Signature

```
`pause`()
```

No arguments. No return value is required.

### Non-interactive

When the session is not interactive, the call does not block and is a no-op: output that surrounds the call is indistinguishable from the same writes with the call omitted.

### Interactive

When the session is interactive, the call writes a short pause message and waits for a key. Execution continues after a key is received. After surrounding payload text is removed, the remainder is distinguishable from a run that never called `pause`. Exact prompt wording is not pinned.

## `optlyn.progressbar`

Import `progressbar` from the package root (`from `optlyn` import `progressbar``). Context manager that wraps an iterable (or a known length without an iterable) and shows advancing progress on a terminal.

### Signature

```
`progressbar`(iterable)
`progressbar`(iterable, hidden=True)
`progressbar`(iterable, label=...)
`progressbar`(iterable, label=..., hidden=True)
`progressbar`(length=...)
`progressbar`(length=..., label=...)
`progressbar`(iterable, length=..., label=...)
```

- `iterable` — items to visit, passed positionally. A sequence or a generator is accepted.
- `length` — known total step count as an integer. When omitted or not a known total, length is unknown. May be supplied together with an iterable to provide or override that total.
- `label` — text shown with the bar.
- `hidden` — `hidden=True` prints nothing. When omitted, the bar is not hidden.

Usable as `with `progressbar`(...) as bar`. The yielded `bar` is iterable: each iteration yields the next original item, in order. Every item is visited when there is no terminal and when the bar is explicitly hidden.

The yielded `bar` also accepts `update` with an integer delta: `update` advances by that many steps rather than one step per item. That form is used with an explicit `length` and no per-item iteration.

### No terminal

Without a terminal, every item is still visited. If `label` is set and the bar is not hidden, that label is printed once. An explicitly hidden bar (`hidden=True`) prints nothing, including no label, and still visits every item.

### Terminal

When attached to a terminal and not hidden, the bar shows advancing progress. Snapshots taken after different numbers of items differ once surrounding payload and the label are removed.

A known integer `length` is distinguishable from an unknown length on a terminal. When `length` is known, a remaining-time estimate is included: the same position after different elapsed times yields distinguishable remainders after surrounding payload and the label are removed. Remaining-time estimate wording is not pinned.

An explicitly hidden bar on a terminal prints nothing: after surrounding payload is removed, the remainder matches a run that never created a bar, and is distinguishable from an advancing unhidden bar.

Irregular advances: with an explicit `length`, `update` of different deltas produce distinguishable terminal remainders after the label is removed.

## `optlyn.prompt`

Import `prompt` from the package root (`from `optlyn` import `prompt``). Standalone helper that asks for a value with a message and a type.

### Signature

```
`prompt`(text, `type`=...)
`prompt`(text, `default`=...)
`prompt`(text, `type`=..., `default`=...)
```

- `text` — the message shown to the user. A plain string is accepted. A value produced by `style` is also accepted.
- `type` — the parameter type used to convert the typed line. A `ParamType` instance is accepted, as is a built-in type such as `INT`.
- `default` — when supplied and `type` is omitted, the conversion type is inferred from this value. A typed line is converted as that inferred type. An integer default infers an integer conversion.

Returns the converted value.

### Observable behavior

Reads a line from standard input and converts it with the given type, or with a type inferred from `default` when `type` is omitted. The converted value is returned to the caller. Conversion works when no command and no parameter are supplied: a direct call still converts. The type’s `convert` may run with `param` and `ctx` omitted.

When called from a command callback, input fed on standard input is consumed as the typed line, and that callback receives the converted value. The author message appears on standard output. Prompt punctuation is not pinned.

### Re-ask and end of file

Conversion failure at the prompt does not finish the invocation as a usage error. The helper asks again until a valid line is given. The first valid line is the result; later lines are not consumed as a second answer. End of file before a valid value is an abort: standalone mode exits with status 1, writes an abort indication on standard error that is distinguishable from a usage error, and does not run the remaining command work.

### Styled text

When the message is produced by `style`, ANSI styling is stripped from that message if the output stream is not a terminal, and kept if the stream is a terminal.

## `optlyn.secho`

Import `secho` from the package root (`from `optlyn` import `secho``). Styled echo: styling plus writing in one step. The observable result matches echoing the string returned by `style` on the same text and color.

### Signature

```
`secho`(message, fg=...)
```

- `message` — the text to style and write.
- `fg` — foreground color, with the same meaning as on `style`. The named color `green` is accepted.

Writes that text to standard output. The original payload characters appear in the written output.

### Color flag on this thread

The same stream and invocation color rules as `echo` apply.

- Force on (`color=True` on the invocation): ANSI styles are kept even when standard output is not a terminal.
- Autodetect (`color` omitted): when standard output is not a terminal, ANSI styles are stripped and the payload text remains.
- Force off (`color=False` on the invocation): ANSI styles are stripped even when standard output is a terminal. The payload text remains.

Plain `echo` of the same payload under the same force-on invocation does not invent those styles. After the payload is removed, the remainder of a `secho` write with a color is distinct from the remainder of a plain `echo` of the same payload.

## `optlyn.style`

Import `style` from the package root (`from `optlyn` import `style``). Wraps text with ANSI styles and returns the new string.

### Signature

```
`style`(text)
`style`(text, fg=...)
`style`(text, bg=...)
`style`(text, bold=True)
`style`(text, dim=True)
`style`(text, underline=True)
`style`(text, overline=True)
`style`(text, italic=True)
`style`(text, blink=True)
`style`(text, reverse=True)
`style`(text, strikethrough=True)
`style`(text, bold=True, underline=True)
```

- `text` — the string to wrap.
- `fg` — foreground color. The named colors `cyan` and `green` are accepted, as is every name in the finite set below.
- `bg` — background color. The same named colors as `fg` are accepted. After the payload is removed, a named `bg` wrap is distinct from a same-name `fg` wrap.
- Independent style switches: `bold`, `dim`, `underline`, `overline`, `italic`, `blink`, `reverse`, `strikethrough`. Each is accepted as a true flag (`bold=True`, and the same true form of each other switch). After the payload is removed, a true switch’s remainder differs from the all-off call (switches omitted). Not all switch remainders are identical. Combining `bold=True` and `underline=True` on one call is distinct from `bold=True` alone and from `underline=True` alone.

Returns a string that contains the original text together with ANSI style sequences. Exact opcodes are not pinned. By default a reset is appended after the payload so styles do not leak into later unstyled text.

### Named colors for `fg` and `bg`

The finite set of named foreground and background colors is: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`, `bright_black`, `bright_red`, `bright_green`, `bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`, `bright_white`, and `reset`.

Each named `fg` wrap is distinct from a call with color omitted. Not all named-foreground remainders are identical. Not all named-background remainders are identical.

Color may also be an integer 0–255 or an RGB triple of three 0–255 integers. Those forms wrap the text: after the payload is removed, the remainder differs from a call with color omitted. Integers 0 and 255 are valid, as is any integer in between.

### Invalid colors

A color that is not a documented name, not an integer in 0–255, and not a triple of three integers in 0–255 fails the call. The call does not succeed as if the color was omitted. That includes a sequence that is not three integers.

### With `echo`

The returned string is suitable for `echo`. Whether those sequences remain on the written stream is decided by `echo` (terminal versus not, and the invocation color flag), not by `style` itself. `style` always returns the wrapped string.

## `optlyn.testing`

The module `optlyn.testing` is imported as `from `optlyn.testing` import …`. Importing it performs no I/O, starts no processes, and opens no sockets.

These names are importable as ``optlyn.testing`.<name>` and as `from `optlyn.testing` import <name>`:

- `CliRunner`

## `optlyn.testing.CliRunner`

Import `CliRunner` from `optlyn.testing` (`from `optlyn.testing` import `CliRunner``). In-process runner that invokes a command with argument tokens and captures output and exit status.

### Signature

```
`CliRunner`()
`CliRunner`(`echo_stdin`=True)
`CliRunner`(`capture`="`fd`")
```

Constructs a runner.

- No arguments — default runner. Authors who only need to invoke a command and read captured output construct it this way. Capture is interpreter-stream capture: writes through the interpreter’s standard streams are recorded; those streams do not expose a real file descriptor. OS-level writes to descriptors 1 and 2 are not recorded.
- `echo_stdin` — when `True`, every standard-input read that actually happened is echoed into captured output, not only prompt echoes. An unread remainder of the supplied input is not copied. A no-argument runner does not echo a consumed non-prompt line.
- `capture` — when the value is `fd`, descriptor capture: OS-level writes to descriptors 1 and 2 are recorded, and interpreter writes are still recorded. A no-argument runner does not record those OS writes.

### `invoke`

```
`invoke`(cli, args=None, `input`=None, `env`=None, `color`=None, `terminal_width`=None, `catch_exceptions`=None, `standalone_mode`=None)
```

- `cli` — the command to invoke.
- `args` — argument tokens as a sequence. An empty list is a run with no extra tokens. Subcommands are selected by including their names in this list (including after a group option).
- `input` — text fed to standard input, consumed as typed lines.
- `env` — mapping of environment variables applied for that run only. A later invoke on the same runner that omits `env` does not see those variables.
- `color` — color setting in force for that run. When `True`, ANSI styles on a styled payload are kept even on a captured non-terminal stream. When omitted, those styles are stripped on a captured non-terminal stream. Unstyled text is not given styles.
- `terminal_width` — extra keyword applied as an invocation-context setting. Different widths rewrap help text differently.
- `catch_exceptions` — when `False`, a callback raise propagates out of `invoke` instead of being returned as a result. When omitted, a raise is caught: `invoke` returns a result that still carries an exit status.
- `standalone_mode` — when `False`, `invoke` still returns a result. A callback raise is then inspectable on that result’s `exception`. When omitted (standalone on) and the raise is caught, `invoke` also returns a result with an inspectable `exception`.

Returns a result object with:

- `exit_code` — process-style status.
- `output` — captured terminal text (standard output and standard error in write order), as a string.
- `stdout` — captured standard output as a string.
- `stderr` — captured standard error as a string, separate from `stdout`.
- `stdout_bytes` — captured standard output as bytes.
- `stderr_bytes` — captured standard error as bytes.
- `exception` — the exception object when a callback raise was caught; false on a successful run. The attribute is readable on the result. Exact exception type names are not pinned.

### `isolated_filesystem`

```
`isolated_filesystem`()
`isolated_filesystem`(`temp_dir`=...)
```

Context manager on the runner. Always creates a new empty directory and changes the current working directory into that created directory. Relative file-parameter reads and writes happen there and do not touch the original working directory.

- No parent — the created directory is removed when the context exits.
- `temp_dir` — a parent path only. The created directory is a child under that parent, not the parent path itself. After the context exits, that child is left in place; the parent is not removed.

### Observable behavior

`invoke` runs the command as a program. A successful callback yields `exit_code` 0. Text the callback writes to standard output appears in `stdout` and `output`. Text written to standard error appears in `stderr` and not in `stdout`. Invoking with `--help` yields `exit_code` 0, help text in captured output, and does not run the command callback. A group invoked with a missing or unknown subcommand token is a usage-class exit 2 with a report on standard error.

`input` is consumed as if typed. Visible prompts echo the typed line into captured output. Hidden prompts do not: the typed secret is absent from captured output.

## `optlyn.unstyle`

Import `unstyle` from the package root (`from `optlyn` import `unstyle``). Removes ANSI style sequences from a string.

### Signature

```
`unstyle`(text)
```

- `text` — a string, which may already contain ANSI styles (including a string returned by `style`).

Returns a string. For a string produced by `style` wrapping a payload, the result equals that payload and contains no ANSI sequences. For a plain payload with no styles, the result equals that payload. Concatenating a styled wrap with later unstyled text, then unstyling, yields the payload plus that later text.

## `optlyn.version_option`

Import `version_option` from the package root (`from `optlyn` import `version_option``). Decorator that attaches an eager version flag. Place it under `command` (or `group`) the same way as `option`.

### Signature

```
`version_option`(version=None, *param_decls, package_name=None, **attrs)
```

- `version` — version identity string to print. `None` (the default) detects the version from an installed distribution.
- `param_decls` — option names. When omitted, the single name `--version` is used.
- `package_name` — distribution or import name used when `version` is omitted.
- `attrs` — forwarded to the underlying option. The flag is eager, is not delivered to the command callback, and does not require other parameters.

Returns a decorator. That decorator attaches the flag and returns the same function (or, if the function is already a command, appends the flag to that command).

### Observable behavior

- Invoking `--version` prints a version identity that contains the supplied `version` string (when one was given) and exits 0. The command callback does not run, even when other required options are missing or are also present on the command line. A run that omits both `--version` and a required option is a usage failure: standalone mode exits 2, and the version identity is not printed.
- When `version` is omitted and `package_name` is given, the identity is that name’s installed-distribution version when the name is an installed distribution. If that name is not an installed distribution, it is treated as an import name, and the identity is the version of the distribution that provides that import. A different installed distribution’s version is not used. A module `__version__` attribute is not used.
- The supplied or detected identity appears on standard output. Exact message wording around that identity is not pinned. The page is not the as-is callback string that `custom_version_option` prints.
- The flag is eager. If both `--help` and `--version` appear on the command line, whichever eager flag the user typed first wins and exits: help first prints the help page and omits the version identity; version first prints the version identity and omits the help-page description.

