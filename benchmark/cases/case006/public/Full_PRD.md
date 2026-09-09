# Optlyn — Full Product Requirements Document

## Product overview

**Optlyn** is a Python package for creating command line interfaces in a composable way with as little code as necessary. It is the “Command Line Interface Composition Kit”: highly configurable, with sensible defaults. It exists so that writing command line tools is quick, and so that an intended command-line API can actually be implemented — including arbitrary nesting of commands — rather than being blocked by the parser.

Optlyn in three points, as the product itself states them:

- Arbitrary nesting of commands
- Automatic help page generation
- Support for lazy loading of subcommands at runtime

The finished product is a **library**, not a command users type. An application author declares commands, groups, options, and arguments; Optlyn parses the process argument list, converts values, generates help, dispatches to the author’s callbacks, and supplies terminal helpers. End users of those applications see a POSIX-style command line: options, positional arguments, nested subcommands, and a help page.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and decorator spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished product. Feature points are ordered so foundational capabilities come first; a later feature point may refine an earlier one only when it says so explicitly.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Command** | A callable unit that parses a slice of the command line and runs an author-supplied callback. A bare command is a leaf: it has options and arguments, but no nested subcommands. |
| **Group** | A command that dispatches to named subcommands (which may themselves be groups). Groups are how Optlyn nests CLIs. |
| **Option** | A named parameter, typically introduced by a dash prefix (`-` or `--`, or another declared prefix). Options are optional unless the author marks them required. They appear fully on the help page. |
| **Argument** | A positional parameter. Arguments are the usual place for files, URLs, and leftover tokens. They are not fully documented on the help page unless the author supplies help text or documents them in the command’s description. |
| **Parameter** | An option or an argument. |
| **Invocation context** | The per-invocation state Optlyn creates when a command runs: parsed values, parent/child linkage, an optional author object, resource cleanup, and flags that affect parsing and output. |
| **Help page** | The usage text Optlyn generates for a command or group when the user asks for help, or when a group is invoked incorrectly under the default “no arguments means help” policy. Layout is Optlyn’s; wording of descriptions is the author’s. |
| **Callback** | The author function attached to a command, group, or parameter. Command callbacks receive converted parameter values. Parameter callbacks receive the converted value and may replace it or refuse it. |
| **Eager parameter** | A parameter that can finish the invocation even when other required parameters are still missing. Help and version flags are eager. If several eager flags appear, the one the user typed first is the one that takes effect. |
| **Default map** | A nested mapping of parameter defaults supplied on the invocation context, used to override declared defaults (for example from a config file) without changing the command definition. |
| **Chaining group** | A group that runs several subcommands in one invocation, in the order they appear on the command line. |
| **Core capability** | A user-observable capability that reflects the product’s design goal; acceptance must prove the real behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

Optlyn is imported and used from Python. The public surface, grouped the way later feature points verify it, is:

- Declaring a function as a command or a group, attaching options and arguments, registering subcommands immediately or later, and invoking the result as a program or as an in-process call.
- Automatic help (default `--help`) and an eager version flag that prints a version identity and exits, including a variant whose identity text is produced by an author callback.
- Built-in parameter types, listed under FP-05; custom types the author supplies.
- Prompts (option-integrated and standalone), confirmation, and hidden password input, including the ready-made password and confirmation option combinations.
- File and path parameters, including `-` as stdin/stdout for the file type.
- Terminal helpers: echo (including to standard error), styling, styled echo, stripping styles, pager output, progress bars, single-character input, pause-until-key, editor launch, application launch, screen clear, application-config directory lookup, filename formatting, and opening files or standard streams.
- Shell completion for Bash (4.4 and newer), Zsh, Fish, and PowerShell, in both registration-script mode and suggestion-emission mode.
- Usage-failure and abort handling with distinct exit-status classes.
- An in-process test runner that invokes a command with argument tokens and captures output and exit status.

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces. Packaging an application as a console-script entry point is how authors ship tools; it is not itself a Optlyn command.

## Non-functional constraints

- **Form factor:** A pure-Python library. Authors build CLIs with it; Optlyn is not a single end-user binary.
- **Language:** Python 3.10 or newer. The package has zero declared runtime dependencies.
- **Platforms:** Intended to work on Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported Python interpreter. No compiled extensions, native code, GPU, or accelerator are required or claimed. (On Windows, when invoked as a program, glob, home-directory, and environment tokens in the process argument list are expanded unless the author disables that; a Unix shell already expands before the process starts. That Windows expansion is not a Linux acceptance obligation.)
- **Hardware:** CPU-only. The mandatory execution substrate is a real host able to import the installed package and run Python.
- **Parsing conventions:** Optlyn implements POSIX-style option parsing (short-option stacking, `--` to end option parsing, long options with `--`). Alternative option prefixes such as `/` and `+` are supported when the author declares them. Leaf commands, by default, also allow an option to appear after a positional argument; groups, by default, do not mix the group’s own options with the subcommand name (FP-03).
- **Help layout:** Description text is customizable; the help **layout** is not a free-form author template. Nested Optlyn programs are meant to keep a consistent help shape when composed.
- **Unicode:** Command-line values are text. Echo and file helpers exist so misconfigured terminals do not fail on ordinary Unicode output. An ASCII-only environment encoding does not abort invocation (FP-11).
- **Threading:** The current invocation context is available on the thread that is running the command. Other threads do not see that context unless the author enters the same context in that thread. The context is not a thread-safe mutable store.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real library behavior matches the described outcomes when a command is invoked with the named inputs (process argument list, environment, standard streams).
- **Absent / hollow:** Decorators that do not parse; help that is a fixed string unrelated to declared parameters; groups that cannot nest; types that accept any string; prompts that never read input; a test runner that does not actually invoke the command.

Cheaper proxies (hard-coded help text, skipping conversion, always succeeding, or substituting a different parser that cannot nest) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces Optlyn’s parser, help generator, or dispatch for a core capability.

**Negative control (Python / package substrate):** When the Optlyn package is deliberately not importable in an isolated subprocess (removed from the import path), an application that depends on it must fail to start with a hard error — not pass silently or skip. When the interpreter is present and the package is installed, the same invocation succeeds. Output-equality alone is not proof that the real package ran.

## Non-goals

- Being a general-purpose argument parser unrelated to command dispatch (Optlyn both parses and dispatches).
- Letting authors fully redesign help-page layout (wording yes; layout no).
- Shipping a remote server, GUI, or web framework.
- Built-in command aliases or plugin discovery. Those are extension patterns authors implement on top of groups (documented as examples); they are not built-in commands of Optlyn itself. FP-06 requires that custom groups *can* resolve names their own way, not that a particular alias scheme ships.
- Thread-safe mutation of an invocation context.
- Guaranteeing color on every Windows console without extra platform support; recent Windows supports ANSI styling, and echo strips styles when the stream is not a terminal.

---

## Feature points

### FP-01: Command declaration, naming, and invocation

**Public entry:** Optlyn’s command declaration (applied to an ordinary Python function) and invoking the resulting command as a program — by calling it, by running it as a script, or as an installed console script. A group’s command-registration helper is also an entry for attaching a leaf command (FP-06).

**Normal behavior:**

- Decorating a function with no extra arguments produces a command whose name is the function name converted to lowercase, with underscores replaced by dashes, and with a trailing `_command`, `_cmd`, `_group`, or `_grp` suffix stripped when present. Passing an explicit name uses that name instead. A function whose name is two words joined by an underscore is therefore invoked with those words joined by a dash.
- Invoking the command with a valid argument list runs the function once and returns a successful process exit when used as a program. The function body is the command’s work: if it writes a greeting to standard output, that greeting appears; if it is not run, that greeting does not appear.
- A command marked deprecated still runs. The help page marks it as deprecated (FP-02). On invocation, Optlyn emits a deprecation warning that is distinguishable from ordinary command output and from a usage failure. A custom deprecation note, when the author supplies one, appears in that warning; the command does not refuse to run merely because it is deprecated.
- Parameters declared on the command are converted and passed into the function under the destination names inferred or declared for those parameters (FP-03). A command with no parameters still runs when invoked with an empty extra-argument list.
- When the command is invoked as a standalone program, Optlyn handles the failure classes in FP-13 and exits the process. When the integrator disables standalone program mode, failures propagate to the caller and the command’s return value is available to the caller instead of being discarded.

**Boundary / error behavior:**

- Unknown option tokens, missing required parameters, and values that fail conversion do not run the command callback. They fail as usage errors (FP-13). The greeting-or-work of the callback is absent in those cases.
- An ASCII-only environment encoding does not abort execution: the same command still runs and produces the same successful outcome as in a Unicode locale.
- Invoking a command with leftover tokens that are not declared as a variadic argument fails as a usage error, unless the command is configured to allow extra arguments (FP-04, unknown-option forwarding).

**Verifiable oracle:**

- Success: a function declared as a command whose name is two words joined by an underscore is invoked with those words joined by a dash (or under an explicit name when one was given); a trailing `_command` (or `_cmd`, `_group`, `_grp`) suffix is stripped from that invoked name; a valid invocation runs the callback exactly once; output produced by the callback is present; a successful standalone run exits zero; a deprecated command still runs and emits a deprecation warning distinct from usage failure.
- Failure / absence: the function never becomes invocable as a CLI; underscores are not mapped to dashes; a `_command` suffix remains in the invoked name; usage errors still execute the callback; standalone invocation neither exits nor reports failure classes; a deprecated command is either refused or runs with no distinguishable deprecation warning.

---

### FP-02: Automatic help pages and eager documentation flags

**Public entry:** The automatic help option on every command (default `--help`, overridable through the invocation context’s help-option names); the command’s docstring and per-option / per-argument help text; the ready-made version option and the ready-made custom-version option; optional epilog, short-help override, metavar, show-default, and show-environment-variable switches.

**Normal behavior:**

- Asking for help on a command prints a help page and does **not** run the command callback. The page includes a usage line, the command’s description, and a documented Options section. Intentional help exits successfully (exit status zero).
- If the function has a docstring, that docstring is the command description, unless the author supplies an explicit help string. A form-feed character in the docstring truncates the help: text after that character is omitted from the help page; text before it remains. The form-feed character itself does not appear on the page.
- Option help strings appear next to those options. Argument help, when the author supplies it, appears in a Positional arguments section. Arguments may also be described in the docstring by name.
- For subcommands listed on a group help page, the short help is the first sentence of the docstring by default, ellipsized if it cannot fit on one line, or an explicit short-help string when the author sets one.
- Group help lists subcommands, the group’s options, positional arguments, and an epilog when one is set. The epilog is printed at the end of the help page.
- The usage line brackets optional elements and leaves required elements unbracketed. A variadic argument is marked with a trailing ellipsis. The default options placeholder is bracketed; an author override of that placeholder is used as given. A group that can run without a subcommand also brackets the leading command token; a chaining group brackets the extra command-and-args unit as optional and repeatable.
- Help text is rewrapped to the terminal width; a maximum content width that defaults to 80 columns and can be raised by the caller caps auto-detected width only, and an explicit caller-supplied terminal width is the wrap width as-is. Single newlines inside a paragraph are not preserved as hard breaks. A paragraph whose first line is only a backspace character is not rewrapped: subsequent lines of that paragraph keep their line breaks, and the backspace line itself is stripped from the rendered help.
- The default metavar for an argument is the argument name in uppercase. For an option that takes a value, the default metavar is the type name in uppercase, unless that type supplies its own placeholder; a flag or counting option has no metavar. Authors may override the usage-line options placeholder and per-parameter metavars.
- When show-default is enabled, the help page shows the default. Show-default may be enabled per parameter or for the whole invocation via the context. The author may supply a custom default description instead of the raw default value. For a single-option boolean flag whose default is off (false), that default remains hidden even if show-default is on. When show-environment-variable is enabled, the associated environment variable name appears on the help page.
- Hidden options, hidden commands, and hidden groups are omitted from help (and from completion — FP-12) but remain invocable if the user types their names.
- Help-option names default to `--help`. The invocation context may replace that list (for example `-h` and `--help`). If an author-declared option reuses every help-option name, the automatic help option is dropped and the author’s option wins; if it reuses only some of those names, the overlapping name runs the author’s option and the remaining names still print help. A parameter merely *named* `help` (for example a positional argument called `help`) does not disable automatic help: both keep working. Authors may also attach an extra help option (for example `-h`) that prints help and exits the same way as the automatic option.
- The ready-made version option is eager: it prints a version identity and exits without running the command callback, even when other required parameters are missing. If the author does not supply the version string, Optlyn tries to detect it from the installed package (and, if the given name is an import name rather than a distribution name, from the distribution that provides that import). The ready-made custom-version option is the same eager flag, except the whole printed identity is exactly the string returned by an author callback that receives the invocation context: that return value is printed as-is, not wrapped in the built-in package/prog/version template or any other surrounding label. If both help and version appear on the command line, whichever eager flag the user typed first wins and exits.

**Boundary / error behavior:**

- Help shown because the user invoked a group with no subcommand under the default “no arguments means help” policy is a **usage failure**, not a successful help request: the help page is printed, the group callback is not run (unless the group is configured to invoke without a command — FP-06), and the exit status is the usage-error class (FP-13), not zero.
- Incorrect usage of a command that causes Optlyn to show help (missing subcommand, and similar no-args-is-help paths) likewise uses the usage-error exit class. Passing `--help` explicitly uses the success exit class.
- A command may disable automatic help. Then `--help` is an unknown option unless the author declared it.

**Verifiable oracle:**

- Success: `--help` on a command that greets does not greet; the page contains the docstring description and declared option help; intentional `--help` exits zero; a form-feed character drops the trailing docstring from help; a backspace-only line preserves line breaks in the following paragraph; a hidden option is absent from help but accepted when typed; `--version` prints a version identity and exits zero without requiring other parameters; a custom-version option prints the author callback’s string and exits the same way; the first of `--help` / `--version` on the command line is the one that takes effect.
- Failure / absence: help runs the callback; help omits declared options; `--help` and a missing-subcommand help path cannot be told apart by exit status; hidden options still appear on the help page; version cannot run unless required options are supplied; a form-feed or backspace marker is either ignored or appears literally on the page.

---

### FP-03: Options

**Public entry:** Optlyn’s option declaration on a command or group. Ready-made combinations that are still options (password option, confirmation option) are specified under FP-08; the version option under FP-02.

**Normal behavior:**

- An option is optional by default. If it is omitted and has no default, the callback receives an absent value. If a default is set, Optlyn infers the type from that default when the author does not set a type (FP-05). A default may be a callable; that callable is invoked when no earlier value source produced a value.
- One option may be declared with several names (a short name and a long name, and additional aliases) that all set the same destination. Long options use a double-dash prefix and may take a value as `--name=value` or `--name value`. Short options use a single dash and a single character. Single-character short flags may be stacked: `-abc` is equivalent to `-a -b -c`. If the last flag in a stack takes a value, that value may be the next token or attached (`-n 5`, `-n5`, `-vn5` when `-v` is a flag and `-n` takes an integer). Multi-character short names are not supported: `-dbg` is `-d`, `-b`, and `-g`, not a single option named `dbg`.
- When the author does not give a destination name, it is inferred from the declared option names: a name that is already a valid identifier wins; otherwise the first long name; otherwise the first short name. A leading dash prefix is stripped and remaining dashes become underscores, so a long name of two words joined by a dash delivers to a two-word identifier joined by an underscore.
- On a leaf command, options and positional arguments may be mixed: `tool file.txt --verbose` is valid and equivalent to `tool --verbose file.txt`. On a group, mixing is off by default: the subcommand name ends that group’s own option parsing, so group options must appear before the subcommand name. Authors may enable or disable mixing.
- An option may be required. Then omitting it is a usage error and the callback does not run.
- Boolean flags: a flag declared as a flag, when omitted, yields false unless the author set a true default; when present, it yields true. An explicit on/off pair (`--shout` / `--no-shout`, or `/debug;/no-debug` when slash is the prefix, or `+w/-w` for plus/minus) yields true for the on token and false for the off token. Several flags may share one destination as a feature-switch group: the callback receives the flag value of the winning flag (see value resolution below).
- A counting option yields how many times it occurred (zero if omitted). Stacked short flags count: `-vvv` is three.
- A repeatable option may be given several times; the callback receives the sequence of values. If it is omitted and has no default, the callback receives an empty tuple, not an absent value. A declared default for a repeatable option must be a sequence (list or tuple) of values, delivered as a tuple when the option is omitted. A multi-value option takes a fixed number of tokens per occurrence (strictly positive; not “consume the rest”). A tuple type on an option sets that arity to the tuple length and converts each position with the corresponding inner type.
- An option may take an optional value: the flag alone yields the author’s flag-value; the flag plus a token yields that token; omitting the flag entirely yields the default.
- Authors may declare prefixes other than `-`, including `/` and `+`.
- Environment variables: an option may name one variable or a list of names (first one set wins). Names are matched exactly (case-insensitive on Windows only) and are not whitespace-trimmed as names. An absent variable, or a variable present with a truly empty value, is treated as not supplying a value (the next source wins). For a repeatable or multi-value option, the type splits a non-empty variable’s string: default split is whitespace; file and path types split on the platform path separator (`:` on Unix, `;` on Windows).
- For boolean flags, environment values are strings interpreted as follows after stripping surrounding whitespace and ignoring case. Activation: `true`, `1`, `yes`, `on`, `t`, `y`. Deactivation: `false`, `0`, `no`, `off`, `f`, `n`. A whitespace-only value strips to empty and deactivates. Any other non-empty string is a conversion usage error, not a silent deactivation. If the flag has a non-boolean flag-value, a variable whose text equals that flag-value also activates; recognized true/false tokens activate or deactivate as above; unrecognized and empty values are treated as unset (the next source wins), not as a usage error. A paired on/off option recognizes only the single environment name the author attached, not a magically derived `NO_*` name.
- A value is filled from command line, then environment, then the default map on the invocation context (FP-07), then the parameter’s declared default; the first of those that produces a value wins. Those four, plus an interactive prompt when one ran (FP-08), are ranked from most explicit to least as: prompt, command line, environment, default map, declared default.
- Feature-switch groups (several options sharing one destination): the option whose source is most explicit wins. Within the default tier, an explicit declared default beats an auto-derived default (bare boolean flags auto-derive default false). If still tied, the last declared option wins.
- A parameter callback sees the converted value and may replace it or refuse it. A refusal is a usage error: non-zero usage-class exit, a message on standard error that distinguishes the failure from success, the command callback not run, and the refused value not delivered. Callbacks run for every source including prompts. An eager flag such as version can finish the invocation even when required non-eager options are missing. A missing parameter still runs its callback, so that callback can default from an earlier parameter’s value. A repeated parameter fires its callback once, with all gathered values.
- A parameter may be hidden from the callback (not passed as a function argument) while still being parsed — used by help, version, and confirmation flags.
- A deprecated option still parses. A deprecation warning is emitted only when the user actually supplied that option, not when the value came only from a default.

**Boundary / error behavior:**

- An unknown option is a usage error, unless the command is configured to ignore unknown options, in which case leftover option-like tokens become extra arguments, which a variadic pass-through argument can collect (FP-04). Unknown long options are left intact. Unknown short options may be split: a known `-v` inside `-va` is consumed and `-a` remains leftover.
- A missing value for an option that requires one is a usage error.
- A bare string (or other non-sequence) default on a repeatable option is a usage error that identifies the option as needing an iterable default; it is not treated as a sequence of characters and not as a single string element. Authors who want one default string must pass a one-element sequence.
- A deprecated option cannot also be required, and cannot use a prompt. Declaring that combination is refused at declaration time.
- Option values belonging to a command must appear after that command’s name and before a nested command name (FP-06). `tool --help sub` is help for `tool`, not for `sub`.

**Verifiable oracle:**

- Success: omitted optional `--name` yields absent or the declared default; `--count=3` delivers integer 3 when the default was an integer; `-vvv` on a counting option yields 3; `-abc` on three flags sets all three; `--shout/--no-shout` delivers true/false respectively; a repeatable `-m a -m b` delivers both messages; an environment variable named by the option supplies the value when the flag is omitted; a command-line value beats that environment value; `tool file.txt --verbose` on a leaf command is equivalent to `tool --verbose file.txt`; unknown `--nope` fails as usage error and does not run the callback.
- Failure / absence: options are required to be positional; stacking does not work; environment values are ignored; command line does not beat environment; unknown options are silently ignored without the ignore-unknown configuration; the callback runs despite a missing required option; a bare string default on a repeatable option is silently split into characters; a boolean environment value other than the documented tokens silently deactivates instead of failing as a usage error; a leaf command rejects an option that appears after an argument.

---

### FP-04: Positional arguments

**Public entry:** Optlyn’s argument declaration on a command or group.

**Normal behavior:**

- An argument is positional. A minimal argument is required, has no default, and is text unless a type or default implies otherwise.
- An argument may be marked optional, or given a default; then omitting it is not a usage error. An argument may declare a fixed positive arity or a variadic arity (consume the rest). Variadic arity may be used at most once on a command. Values are delivered as a sequence when arity is not one. A variadic argument omitted yields an empty sequence unless it was marked required.
- After a `--` token, subsequent tokens are arguments even if they look like options (`-- -foo.txt bar.txt` yields those two filenames).
- Arguments may read from environment variables only when the author names those variables explicitly (one name or a list; first set wins). There is no automatic environment prefix for arguments (that prefix applies to options — FP-07). An absent or truly empty variable is treated as not supplying a value. A non-empty variable for a non-unary argument is split the same way as for a multi-value option (FP-03).
- Argument help is optional. Without it, the help page’s main description is where authors document them; with it, a Positional arguments section lists them (FP-02).

**Boundary / error behavior:**

- A missing required argument is a usage error and the callback does not run.
- Extra tokens beyond declared arity, when no variadic argument collects them and extra arguments are not allowed, are a usage error.
- With ignore-unknown-options enabled, option-shaped tokens may be consumed as arguments without needing `--`.
- A deprecated argument still parses and cannot be required. Declaring that combination is refused at declaration time. A deprecation warning is emitted only when the user actually supplied that argument, not when the value came only from a default.

**Verifiable oracle:**

- Success: `copy src a b` with a single source argument and a variadic destination argument delivers `src` and the sequence `a, b`; `touch -- -foo.txt` delivers `-foo.txt` as an argument, not as an unknown option; an argument with an explicit environment name uses that file or value when the position is omitted; an optional argument omitted is not a usage error.
- Failure / absence: positions are treated as options; `--` does not protect option-shaped names; missing required arguments still run the callback; two variadic arguments on one command parse ambiguously or are both accepted as independent “consume rest” fields; an optional argument is treated as required.

---

### FP-05: Parameter types and conversion

**Public entry:** The type attached to an option or argument, or inferred from a default. Built-in types are a fixed finite set. Authors may also supply a custom type.

**Normal behavior:**

Built-in types:

- **String** — the default; Unicode text.
- **Integer** — only integers; conversion failure is a usage error.
- **Float** — only floating-point numbers.
- **Boolean** — used automatically for boolean flags. Text conversion (case-insensitive) treats `1`, `true`, `t`, `yes`, `y`, `on` as true and `0`, `false`, `f`, `no`, `n`, `off` as false.
- **UUID** — accepts UUID text and yields a UUID value. It is never inferred automatically from a default.
- **Choice** — a closed list of allowed values, or the member names of an enumeration. The value delivered is the original choice object (enumeration member or original list entry), not merely the matched string, even when matching is case-insensitive. If two choices normalize to the same token, the first registered original is delivered. Repeatable choice options are allowed; a default for a repeatable choice must be a sequence of valid choices.
- **Date-time** — parses into a date-time value. Formats are tried in order; the first success wins. The default format list is the finite set: date `YYYY-MM-DD`; date and time with `T` as `YYYY-MM-DDTHH:MM:SS`; date and time with a space as `YYYY-MM-DD HH:MM:SS`. Authors may replace that list. These defaults are not timezone-aware.
- **Integer range** — an integer that must lie in an optional minimum/maximum range. Bounds are closed by default; either side may be open (boundary excluded) or omitted (unbounded). With clamp enabled, a value outside the range is replaced by the nearest included boundary instead of failing.
- **Float range** — the same range rules for floats. Clamp is only allowed when both bounds are closed.
- **Tuple** — a fixed-length product of inner types, one converted value per position (see multi-value options in FP-03).
- **File** — opens a file; see FP-09.
- **Path** — validates a filesystem path and returns the path (not an open file); see FP-09.
- **Pass-through** — does not convert the token (used when leftover raw tokens must be forwarded).

A custom type converts a string to a value and must pass through a value that is already the right type (so defaults and Python-side calls work). A conversion function that fails on invalid input is also accepted as a type. Conversion must work even when no command or parameter is supplied (prompt-time conversion). Failure of conversion is reported as a usage error that identifies the offending parameter, not as an uncaught crash.

Help pages include type-driven details (for example listing choice values).

**Boundary / error behavior:**

- A value that cannot convert (integer `x`, choice `foo` when only `md5` and `sha1` are allowed, date-time that matches none of the formats, range 12 when the range is 0–9 without clamp) is a usage error: non-zero usage-class exit, message on standard error that distinguishes this failure from success, callback not run.
- Integer range with clamp: `--count=100` on a 0–20 clamped range delivers 20 and runs the callback. Without clamp, the same input is a usage error.
- Float range refuses clamp when a bound is open (declaration error).
- Choice matching after case-folding still returns the originally registered choice, so an enumeration member remains that member.

**Verifiable oracle:**

- Success: `--n 3` with an integer-typed or integer-default option delivers integer 3, not the string `"3"`; `--hash-type=md5` with a case-insensitive enumeration choice delivers the original member; `--count=100` on a 0–20 clamped integer range delivers 20; `--when=2020-01-02` succeeds under the default date-time formats; `--when=not-a-date` fails as usage error.
- Failure / absence: all values remain strings; out-of-range values are accepted without clamp; choice returns a lowercased string instead of the registered object; invalid input crashes instead of a usage error; the callback runs with a half-converted value.

---

### FP-06: Groups, nesting, and deferred subcommand loading

**Public entry:** Optlyn’s group declaration; attaching commands with the group’s command helper or by registering an already-declared command later; custom groups that override how names are listed and resolved; a command collection that presents subcommands gathered from several groups.

**Normal behavior:**

- A group contains named subcommands. Invoking `tool initdb` runs the `initdb` callback. By default, invoking the group with no arguments does not run the group callback and shows help as a usage failure (FP-02, FP-13).
- The group callback **does** run when a named subcommand is dispatched, including when that child then shows help or version; group-level help or version still skip the group callback and do not dispatch. Nested groups run from the outside in: `cli session initdb` runs the `cli` group, then `session`, then `initdb`.
- Parameters belong to the command they were declared on. Group options must appear before the subcommand name; subcommand options after it. `tool sub --help` is help for `sub`; `tool --help sub` is help for `tool` and does not run `sub`.
- Arbitrary nesting is allowed: groups containing groups containing commands. Every group on the path must be invoked to reach a nested command.
- Commands may be registered later, including from another module. Invocation does not depend on whether attachment was immediate or delayed.
- A group may be configured to run even when no subcommand is named. Then the group callback runs, and the invocation context reports whether a subcommand is about to run so the callback can distinguish “group only” from “group then child”.
- A group may be configured so that no arguments does not mean help (the default for groups is that it does). A leaf command may be configured so that no arguments *does* mean help (the default for leaves is that it does not).
- Lazy loading: a group may resolve a subcommand name only when that name is needed — listing commands, generating help (short help for immediate children), completing names (FP-12), or dispatching. A child that is not needed is not loaded. Custom listing and lookup are the supported extension points; Optlyn does not ship a particular plugin folder format, but a custom group that loads a command from a named module when first requested must then invoke that command the same as an eagerly attached one.
- A command collection exposes the union of subcommands from several source groups under one dispatch surface.
- Hidden commands and hidden nested groups are omitted from the parent help listing but remain reachable by name.
- Command names may be given explicitly, independent of the function name (FP-01).

**Boundary / error behavior:**

- An unknown subcommand name, or a parsed invocation that leaves no subcommand name (group options or arguments only) when the group is not configured to invoke without a command, is a usage error and does not run the group callback or any child. Those two failures report a missing or unknown command; they do not use the no-arguments help page.
- A chaining group (FP-10) cannot nest further groups beneath it.
- Resolving `cli bar baz` loads `bar` then `baz`. Help for `cli` loads immediate children, not grandchildren.

**Verifiable oracle:**

- Success: a group with `initdb` and `dropdb` runs the matching callback and not the other; group options do not leak into the child callback; `session initdb` under `cli` runs both group layers then the leaf; a command registered after declaration is indistinguishable at invocation from one attached immediately; a group set to invoke without a command runs its callback on empty args and still runs it before a named child; a custom group that defers import of `foo` runs `foo` when requested and does not import it merely because an unrelated sibling was requested.
- Failure / absence: only a flat command list works; parent options must be repeated on the child; late registration is ignored; empty group invocation runs a leaf or exits zero without help; deferred loading either never resolves the child or imports every child at group import time with no way to tell them apart.

---

### FP-07: Invocation context, defaults, environment prefix, and value sources

**Public entry:** The invocation context created for each command run; opting a callback into receiving that context; storing an author object on the context for children; the default map; an automatic environment-variable prefix; asking which source supplied a parameter; registering resources to close when the invocation ends; a token-normalization function; invoking or forwarding another command from inside a callback.

**Normal behavior:**

- Each invocation creates a context linked to its parent. Children see the parent chain. An author object stored on the context is passed to children unless a child replaces it. A callback may request the context as its first argument, or request the author object, or request an object of a given type found on the parent chain (created empty if the author asked to ensure it).
- Automatic environment prefix (options only): when the top-level invocation is given a prefix, each option may be filled from a variable built as prefix, then each command name, then the parameter name, all uppercased and separated by underscores, with dashes in names turned into underscores. Example: prefix `WEB`, subcommand `run-server`, option `host` → `WEB_RUN_SERVER_HOST`. A top-level command with prefix `GREETER` and option `username` → `GREETER_USERNAME`. An individual option may opt out of that automatic prefix and then is filled from the prefix-built name only if the author also named that variable explicitly.
- The default map overrides declared defaults. It nests by subcommand name. A string in the default map is split the same way environment values are (FP-03) only when that parameter’s per-occurrence arity is not one (a multi-value option or tuple type); a sequence is used as-is. A default-map string for a repeatable option that takes one value per occurrence is not split and is refused as not an iterable sequence, the same usage error as a declared default (FP-03). The map may be passed at invocation or set as a context default on the command declaration.
- An integrator can ask which source supplied a named parameter. The distinguishable sources are: prompt, command line, environment, default map, and declared default. Command-line `8080` for a port, environment `PORT=8080` with no token, and a declared default of 8080 with neither, are three different sources even when the numeric value is the same.
- Resources opened for a group can be registered on the context so they stay open through subcommands and are closed when the CLI invocation ends — including on process exit of that command.
- Token normalization applies to option names, choice values, and command names. A lowercase normalizer makes `--NAME` match `--name`.
- One command may invoke another with explicit values, or forward to another filling in the current parameters. Forwarding runs the target with this command’s values; invoke supplies the caller’s chosen values.
- Within the running thread, the current context can be read (for example so echo can inherit the color flag). Other threads do not see it unless the context is entered there.
- The invocation may force color on, force color off, or leave autodetection (FP-11).

**Boundary / error behavior:**

- Automatic prefix never invents environment names for arguments (FP-04).
- A value that did not go through a declared parameter is not converted and is not reported as coming from a tracked source; stuffing extra keys is not a substitute for declaring the parameter.
- Resource cleanup runs when the invocation finishes. A file type closed at the end of a chained command is not usable later in a pipeline processor (FP-10).

**Verifiable oracle:**

- Success: a child command reads the debug flag stored on the parent context’s author object; with prefix `GREETER`, omitting `--username` while `GREETER_USERNAME=john` is set delivers `john`; a default map whose nested entry for the `runserver` subcommand sets port to 5000 is used when `--port` is omitted and is overridden when `--port 8000` is given; source detection reports command line vs environment vs default for the same numeric port; `--NAME=Pete` works when a lowercase token normalizer is installed and fails as unknown option without it; an option that opted out of the automatic prefix is not filled from the prefix-built name.
- Failure / absence: children cannot see parent state; prefix is ignored or applied to arguments; default map cannot override; source detection cannot tell command line from default; token normalization is always on or always off with no author control.

---

### FP-08: Prompts, confirmation, and hidden input

**Public entry:** Option-integrated prompts; the standalone prompt and confirm helpers; the ready-made password option (hidden input plus confirmation); the ready-made confirmation option (a yes flag that prompts when omitted and aborts when the user declines).

**Normal behavior:**

- An option with prompting enabled, if not supplied on the command line, reads a line from the user (standard input) and uses that as the value, after conversion (FP-05). A custom prompt string replaces the default prompt derived from the option name. Command-line supply skips the prompt.
- If the author does not require a prompt merely because the option was omitted, the option does not prompt when fully omitted; it prompts when the flag is present without a value (and still uses the default when fully omitted). If the option is also required, it prompts both when omitted and when the flag is present without a value.
- A declared default (static or callable) and a default-map value still prompt — they are shown as the default and used if the user answers with an empty line — while an environment value fills the option and skips the prompt.
- Standalone prompt asks for a value with a message and a type (or a type inferred from a default). Standalone confirm asks a yes/no question and returns a boolean. Confirm may be told to abort the program when the answer is no (FP-13 abort class). Standalone prompt and confirm strip ANSI styles from the prompt text when the output stream is not a terminal, matching echo (FP-11).
- Hidden input does not echo the typed value. A confirmation prompt asks twice and rejects a mismatch by asking again. The password option is that combination: prompt, hide input, confirm.
- The confirmation option adds a boolean flag (by default a yes-style flag). If the user passes the flag, the command runs without a question. If the user omits it, Optlyn asks; a negative answer aborts without running the command callback; a positive answer runs it.
- Prompts re-ask on conversion failure until a valid value is given or the input stream ends.

**Boundary / error behavior:**

- Combining deprecated with prompt is refused (FP-03).
- End of file during a prompt becomes an abort (FP-13).
- In the test runner (FP-14), supplied input is consumed as if typed; hidden input is not echoed back into captured output; visible prompts are.

**Verifiable oracle:**

- Success: a command with a prompted `--name` and no `--name` on the command line reads `John` from input and greets John; the same command with `--name=John` does not wait for input; a password option with matching hidden lines accepts and does not echo the secret into output; a confirmation option without `--yes` and a negative answer does not run the destructive callback; with `--yes` it runs without reading a question answer.
- Failure / absence: missing options never prompt and silently pass absent values; secrets appear in output; declining confirmation still runs the callback; command-line values still prompt.

---

### FP-09: File and path parameters

**Public entry:** The file parameter type and the path parameter type on options or arguments; the helper that opens a file or a standard stream with the same dash-as-stdin/stdout rule; atomic and lazy open modes. The helper opens immediately unless the caller turns lazy on.

**Normal behavior:**

- File type: the value is an open file. The default mode is reading. The token `-` means standard input when the file is opened for reading and standard output when opened for writing. Text and binary modes are supported; a text file uses a declared encoding when the author sets one. Files opened for reading (and standard streams) open immediately so a missing file fails before work starts. Files opened for writing open on first I/O by default (lazy), so a write-mode file is not truncated until actually used. Lazy mode can be forced on or off. Atomic mode writes to a sibling temporary file and replaces the target on completion.
- Path type: the value is a path, not an open file. Optional checks, each independently selectable: the path must exist; files allowed; directories allowed; readable; writable; executable; resolve to an absolute path (symlinks resolved; a leading tilde is not expanded). A dash may be allowed as a path token meaning a standard stream without opening it. The author may request the path be produced as a particular path object type.
- Environment lists of file or path values split on the platform path separator (FP-03).
- Filename formatting converts a path that may not be Unicode into text that can be printed without failing.

**Boundary / error behavior:**

- A file that cannot be opened while converting the parameter (missing read target, or a non-lazy write that cannot open) is a usage error that identifies the path; the callback does not run. A lazy write that fails when I/O starts is a general file-open error (not the usage-error class) that also identifies the path.
- Path checks: a missing path fails when existence is required; a directory fails when only files are allowed; a non-executable path fails when executable is required. If existence is not required and the path is missing, further permission checks are not applied.
- Standard input/output returned from the open helper do not close the real process streams when the caller’s block ends; a real file does close.

**Verifiable oracle:**

- Success: copying with input `-` and output `hello.txt` writes stdin bytes to that file; then copying that file to `-` prints the same bytes; a path type with existence required accepts a created `hello.txt` and rejects `missing.txt` as a usage error; an atomic write leaves the original file intact until that file is closed, then replaces it with the written content.
- Failure / absence: `-` is treated as a literal filename and does not read stdin; missing files crash without a usage/file error; path existence checks are ignored; opening `-` for write closes process stdout.

---

### FP-10: Command chaining and pipelines

**Public entry:** A group declared as a chaining group; an optional result callback on that group that receives subcommand return values.

**Normal behavior:**

- A chaining group runs more than one subcommand in one command line, in the order given: `my-app validate build` runs `validate` then `build`. Each subcommand’s options must appear before its arguments.
- The group’s result callback, if registered, runs after the chain. In chain mode it receives the list of subcommand return values plus the group’s own parameters (an empty list when no subcommand ran). In non-chain mode it receives the single subcommand return value, or the group’s own return when no subcommand ran. Return values are otherwise ignored when the group is a standalone program.
- If the chaining group is also set to invoke without a command, an empty pipeline still runs the result callback instead of showing help. (A common author pattern, not itself a built-in command, is for subcommands to return processor callables that the result callback applies in order to an input stream; an empty pipeline can then copy input unchanged.)
- When chaining, asking the invocation context for the current subcommand name does not yield any one child’s name; the value is distinguishable from a single child name and from “no subcommand”.

**Boundary / error behavior:**

- Only the last command in a chain may use a variadic (consume-rest) argument; a consume-rest argument on a non-last command is not refused at declaration, but it consumes the remaining tokens so later command names are not dispatched.
- Groups cannot be nested under a chaining group: attaching a group beneath a chaining group is refused at declaration time.
- Files opened as a chained subcommand’s parameter type are closed when that subcommand’s callback returns, so later pipeline processors must not use them; the chaining group’s own files stay available to the result callback.

**Verifiable oracle:**

- Success: `validate build` prints (or otherwise performs) validate’s work then build’s work, in that order, in one invocation; a result callback sees both return values as a list; an empty chain on a group that invokes without a command runs the result callback with an empty list rather than usage-help; `lower` then `show` on a shared name transforms then prints.
- Failure / absence: only the last subcommand runs; a second name is treated as an unknown argument of the first; result callbacks never see return values; nesting a group under a chain is accepted and then mis-parsed.

---

### FP-11: Terminal output and interaction helpers

**Public entry:** Echo (including to standard error), styling, styled echo, unstyling, pager output (including a writable pager stream), progress bars, reading a single character, pause until a key, launching an editor, launching an application or locating a file in the file manager, clearing the screen, looking up a per-user application config directory, opening files/streams (shared with FP-09), and binary/text standard-stream accessors.

**Normal behavior:**

- Echo writes text or binary to standard output by default, with a trailing newline unless suppressed. It can write to standard error instead. It is robust to misconfigured terminals where ordinary printing of Unicode would fail. When the stream is not a terminal, ANSI styles in the text are stripped; when it is a terminal, styles are kept. The invocation may force color on (styles kept even when the stream is not a terminal), force color off (styles stripped even on a terminal), or leave autodetection.
- Styling wraps text with ANSI styles. Named foreground/background colors are the finite set: black, red, green, yellow, blue, magenta, cyan, white, bright_black, bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan, bright_white, and reset. Color may also be an integer 0–255 or an RGB triple of three 0–255 integers. Independent style switches: bold, dim, underline, overline, italic, blink, reverse, strikethrough. By default a reset is appended so styles do not leak. Invalid color values fail rather than being ignored: a color that is not a documented name, not an integer in 0–255, and not a triple of three integers in 0–255 fails the style call, including a sequence that is not three integers; that call does not succeed as if the color was omitted. Styled echo is echo plus styling in one step. Unstyling removes ANSI sequences.
- Pager output writes long text to standard output through a pager when the environment supports one. When not interactive, the text is written to standard output without launching a pager. Authors may pass a complete string, an iterator of chunks, or a writable pager stream. Chunked pager output is flushed as it is written so a generator is not held until the pipe fills. Styles are kept or stripped according to what that destination supports. A pager that writes to the process standard output does not close that real stream when it finishes.
- A progress bar wraps an iterable (or a known length without an iterable) and, when attached to a terminal, shows advancing progress and remaining-time estimate when length is known. Every item is still visited when there is no terminal or when the bar is explicitly hidden. Authors may set a label: with no terminal that label is still printed once; an explicitly hidden bar prints nothing. Irregular advances use an explicit length and an update of a delta rather than one-step-per-item.
- Single-character input reads one character from the terminal even if standard input is a pipe. Interrupt and end-of-file key sequences become interrupt and end-of-file failures, not raw characters.
- Pause prints a short message and waits for a key when interactive; when not interactive it does nothing.
- Editor launch opens the user’s editor on a string (returns the saved text, or absent if the user quits without saving) or on a filename (no returned text).
- Application launch opens a URL or filename with the default associated application, and can open a file manager with the file selected.
- Screen clear clears the visible terminal; when not connected to a terminal it does nothing.
- Application directory: given an application name, the path is the platform config location. For an app named `Foo Bar`: on macOS, `~/Library/Application Support/Foo Bar`; on Unix, `~/.config/foo-bar` (or `$XDG_CONFIG_HOME/foo-bar` when that variable is set); on Windows, the roaming or local application-data folder plus `Foo Bar`. A POSIX-forced mode uses `~/.foo-bar` on POSIX systems instead.

**Boundary / error behavior:**

- Echo to a non-terminal strips styles; echo to a terminal keeps them. That distinction is observable by inspecting whether ANSI sequences remain in the bytes when the stream is a pipe versus a tty. Forced color on or off overrides that autodetection.
- Progress bars do not require a tty to iterate; they must not skip items when there is no terminal or when explicitly hidden.
- Pause must not block in non-interactive runs.
- Invalid style colors raise an error at the helper call, distinct from writing the original unstyled text.

**Verifiable oracle:**

- Success: echo of `Hello` produces that line on stdout; echo with the error-stream flag produces it on stderr and not stdout; styled green text contains style sequences on a tty-like stream and does not contain them when echoed to a captured non-tty stream; a two-integer color sequence fails the style call rather than being ignored; a progress bar over three items visits all three; application directory for `Foo Bar` on Linux is the config home joined with `foo-bar` (spaces to dashes, lowercased).
- Failure / absence: echo cannot write Unicode; styles leak onto pipes; progress bars drop items when not a tty; application directory ignores the platform layout; pause hangs in non-interactive tests; an invalid color is written as unstyled text.

---

### FP-12: Shell completion

**Public entry:** Completion mode on an installed executable, selected by an environment variable whose name is underscore + the executable name in uppercase with dashes turned into underscores + `_COMPLETE`. Built-in shells are the finite set: `bash`, `zsh`, `fish`, `powershell`. Two instruction families exist: `{shell}_source` prints the script the user sources to register completion; `{shell}_complete` prints suggestions for the current incomplete token.

**Normal behavior:**

- Completion mode uses the invoked executable name, so `python some_script.py` ignores a completion variable named for a different installed executable and the command runs normally.
- After registration, completing a command name suggests subcommands. Completing after a dash suggests option names. A choice type suggests only its allowed values that match the incomplete prefix. File and path types do not list filesystem entries as ordinary suggestions: they ask the shell to complete paths, and a path type that allows directories but not files asks for directories only. Hidden commands and hidden options are not suggested. Options are listed only once at least a dash has been typed.
- Built-in source modes: `bash_source`, `zsh_source`, `fish_source`, `powershell_source`. Each prints a shell-specific script, not the application’s normal command output, and does not run the command callback.
- Built-in complete modes: `bash_complete`, `zsh_complete`, `fish_complete`, `powershell_complete`. Each reads the incomplete command line from that shell’s completion environment (the word list and which word is incomplete) and writes suggestions, then exits without running the command callback. The suggestion stream is distinguishable from ordinary command output and from the registration script.
- Authors may attach a completion function to a parameter, or implement completion on a custom type. Suggestions may include a help string. Zsh and Fish display that help next to the value; Bash and PowerShell still suggest the value without requiring that help to appear. A completion function receives the current context, the parameter, and the incomplete token (possibly empty).

**Boundary / error behavior:**

- An incomplete token that matches nothing yields an empty suggestion list, not a usage error.
- Hidden names that are omitted from suggestions remain valid if fully typed (FP-02, FP-06).
- An unrecognized instruction value for the completion variable is not treated as a successful source or complete run: the command callback does not run, and the process prints neither a registration script nor a suggestion stream.

**Verifiable oracle:**

- Success: with the completion variable set to `bash_source` (and the matching executable name), the process prints Bash completion script text and does not run the command’s callback; with the variable set to `bash_complete` and an incomplete line at a group, the process prints suggestions rather than running the callback; completing an empty token at a group lists visible subcommand names and not hidden ones; completing `-` lists visible option names including `--help` and not hidden options; a choice type suggests only its allowed values that match the incomplete prefix; a file or path type yields a path-completion suggestion that carries the incomplete token rather than a listing of directory entries.
- Failure / absence: the completion variable is ignored and the command runs normally; hidden commands appear as suggestions; choice values are not suggested; source mode prints nothing distinguishable from ordinary help; complete mode cannot be told apart from source mode or from a normal run.

---

### FP-13: Usage failures, abort, and exit status

**Public entry:** Standalone program invocation of any command or group; author-initiated abort (including from confirm); conversion and usage failures from FP-03–FP-09.

**Normal behavior:**

When run as a standalone program:

- Success (callback completed, or intentional help/version that exited after printing) yields exit status **0**. An author-requested clean stop from inside a callback also uses status 0 unless the author supplied a different status.
- Usage errors — unknown option, unknown subcommand, missing required parameter, conversion failure, incorrect combination — yield a usage-error exit status (**2**). A message is written to standard error that distinguishes the failure from success. The command callback does not run. When the error is “group invoked with no subcommand” under default no-args-is-help, the help page is also shown (FP-02).
- Abort — user declined a confirming abort, end-of-file on a prompt, keyboard interrupt translated into abort, or an author abort — yields a non-zero abort-class exit (**1**), writes an abort indication to standard error that is distinguishable from a usage error and from success, and does not run the remaining command work.
- Other Optlyn-signaled user errors that are not usage errors use a general error exit (**1**) and show an error description on standard error.

When standalone program mode is disabled, those failures propagate to the integrator and the process is not implicitly exited; return values bubble to the caller (FP-01, FP-10).

**Boundary / error behavior:**

- Intentional `--help` is status 0; missing-subcommand help is status 2. Those two must not be collapsed.
- Keyboard interrupt and end-of-file are treated as abort in standalone mode, not as success.
- A usage error identifies the offending parameter when the failure is about a parameter (bad value, missing required), as distinct from an unknown option/command failure.

**Verifiable oracle:**

- Success vs usage vs abort: a valid greet exits 0; `--help` exits 0 and does not greet; a group with subcommands invoked with no arguments exits 2 and shows help without running a leaf; `--unknown` exits 2; declining a confirm-with-abort exits 1 with an abort indication and does not run the protected callback. The three classes (0, 2, 1-with-abort) are mutually distinguishable.
- Failure / absence: all failures exit 0; help-on-error and `--help` share exit 0 so tests cannot tell them apart; abort still runs the callback; usage errors crash with an uncaught traceback instead of a usage-class exit.

---

### FP-14: In-process testing runner

**Public entry:** Optlyn’s testing helpers: a runner that invokes a command with a list of argument tokens (and optional input, environment, program name, terminal width, color, and context settings) and a result object; an isolated-filesystem helper.

**Normal behavior:**

- Invoking a command through the runner executes that command as if from the command line and returns a result that exposes: exit status, captured standard output (text and bytes), captured standard error when separately available, and any exception when not in standalone mode. Assertions against greetings, help text, and exit status in this document are meant to be made against that result.
- Subcommands are selected by including their names in the argument token list (for example the debug option followed by the subcommand name `sync`).
- Extra keywords on invoke are passed as invocation-context settings (for example a fixed terminal width).
- Isolated filesystem: a context that sets the current working directory to a new empty directory. File-parameter commands can create and read files there without touching the rest of the disk. When no parent is given, the runner removes that directory on exit; when a parent path is supplied, the new directory is created under that parent and is left in place.
- Input supplied to invoke is fed to standard input. Visible prompts echo the typed line into the captured output; hidden prompts do not. An optional runner mode also echoes every standard-input read into captured output, not only prompt echoes.
- Capture has two modes: interpreter-stream capture (default), which records writes through the interpreter’s standard streams; and file-descriptor capture, which records OS-level writes to descriptors 1 and 2. Default capture does not provide a real file descriptor on those streams. Authors who need a real descriptor opt into descriptor capture. File-descriptor capture is not available on Windows.

**Boundary / error behavior:**

- The runner is for tests. It changes interpreter state and is not thread-safe.
- If the command raises and standalone mode is on, the result still carries an exit status rather than necessarily raising out of invoke (unless the runner is told not to catch those exceptions). Integrators can inspect the exception on the result.
- Isolated filesystem does not by itself mock Optlyn; commands that write files must actually write them inside the sandbox.

**Verifiable oracle:**

- Success: invoking a hello command with token `Peter` yields exit 0 and output that greets Peter; invoking with `--help` yields exit 0, help text, and no greeting; isolated filesystem plus a file argument reads a file created only in that directory; prompt tests see the prompt and the echoed visible input; hidden password input does not appear in captured output.
- Failure / absence: invoke does not run the command; output is always empty; exit status is always 0; isolated filesystem still writes to the original working directory; no way to feed prompt input.

---

## Cross-cutting refinements

- **FP-02 vs FP-13:** Intentional help is a successful documentation request (exit 0, callback skipped). Help shown because the invocation was incorrect is a usage failure (exit 2). Later tests must keep that split; collapsing it would make FP-02’s success path and FP-13’s usage path indistinguishable.
- **FP-03 vs FP-07 vs FP-08:** The same option may be filled from command line, environment, default map, declared default, or prompt. FP-03 states precedence; FP-07 states prefix and source inspection; FP-08 states when a prompt actually runs. A command-line value must never prompt; a callable default may still prompt.
- **FP-06 vs FP-10:** Nesting is the default group behavior. Chaining is an explicit group mode that forbids nested groups and changes return-value shape. FP-10 refines FP-06 only for groups declared as chaining.
- **FP-09 vs FP-11:** Opening `-` as a file parameter and opening `-` through the file-open helper obey the same stdin/stdout rule.
- **Hidden names:** Omitted from help (FP-02) and completion (FP-12), still dispatchable (FP-06) and still parsed (FP-03).
