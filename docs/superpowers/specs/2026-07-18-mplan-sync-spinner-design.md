# mplan Sync Spinner Design

## Goal

Show a continuously animated status indicator while TUI synchronization is running, followed by the existing success counts or failure message.

## Behavior

- `:s` and `:sync` display a Unicode braille spinner followed by `正在同步…`.
- The spinner advances approximately every 100 milliseconds until synchronization completes.
- Keyboard input is paused during synchronization so duplicate operations cannot overlap.
- Success replaces the spinner with the existing imported/exported/updated counts.
- Failure replaces the spinner with the existing error text and leaves the application open.
- `:sq` and `:syncquit` use the same spinner, exit after success, and remain open after failure.
- The standalone `mplan sync` command keeps its current non-animated output.

## Architecture

The TUI starts `SyncEngine.sync_month` in one background thread. The main thread remains responsible for rendering and updates a copied application state with successive spinner frames. The worker captures either the `SyncReport` or the raised exception, and the existing result-formatting logic produces the final state.

No store or Calendar calls are duplicated, and no input-reading thread is introduced.

## Verification

Tests use a controllable worker and renderer to verify multiple distinct frames, success formatting, failure formatting, `syncquit` exit semantics, and preservation of the standalone CLI behavior. The full test suite and global `mplan` entry point are verified before publishing.
