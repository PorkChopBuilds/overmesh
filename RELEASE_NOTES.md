# OverMesh Release Notes

## 2026.10.11.2

### Fixed

- Messages heard directly from a nearby radio no longer show a "path likely" badge when OverMesh can confirm the packet.

## 2026.10.11.1

This is a housekeeping release. There is nothing new to learn, but a lot of small things that were wrong, unclear or quietly broken are now fixed.

### Fixed

- On-screen text no longer contains em dashes. The long dashes used in labels, tooltips, pop-ups and error messages are gone, so the interface reads cleanly and the same way everywhere.
- Settings toggles now treat the text "false" as off. A caller sending a boolean as text (curl, Home Assistant, a script) used to switch the flag on no matter what it said.
- Silent Running now also blocks GPS pushes and automatic GPS pushes, matching every other transmit path.
- The Automation Bridge works while a login is enabled. It was answering 401 before its own token was ever checked, which broke the documented Home Assistant setup.
- The Sense button on cooldown now shows the remaining time instead of doing nothing visible.
- Ignore and Mute now report a failure instead of changing the row locally and then snapping back on the next refresh.
- A failed map DM send keeps your typed text and shows what went wrong.
- Chat and map send errors now show the server's own message instead of raw JSON.
- OM Lite Log import works again. It was uploading a file the server could not read.
- The OM Lite Sense toggle no longer starts inverted and now follows the server's actual state.
- Bad input to passive-observation cleanup and contact notes now returns a clear 400 instead of an error page.

### New and improved

- A yellow update banner across the top of the page tells you when a newer OverMesh release is available, showing the available and installed versions, an "Open updates" button and a dismiss X. Dismissal is remembered per release, so silencing one release does not hide the next one. OM Lite shows the same banner.
- The New Mark / Self Note dialog is network-aware. On a MeshCore-only map it offers just the Self Note tab, because MeshCore has no waypoint message; on Meshtastic it shows the "Mark (MT waypoint)" tab. The Self Note tab can also add the note to the Log.
- The MeshCore message badge is now honest about how sure OverMesh is that it matched a received packet to a message. It says "path unconfirmed" when the packet could not be confirmed, instead of showing a confidence that was almost always low.

### Removed

- The parked Cross-system forwarding feature has been removed. It was never enabled, so nothing changes for a normal install, and a stored cross configuration key is simply ignored from now on.
- Three dead API endpoints, a do-nothing "RC collector obs count" alert toggle, and two vendored JavaScript files that nothing referenced were removed.

---

## Earlier notes

This is the point where OverMesh stops being just the older Meshtastic dashboard with some MeshCore work around it, and becomes the real MT plus MC app.

The main change is simple: Meshtastic and MeshCore now live in one interface and are treated as equal parts of the same tool. The app is still local first, still self-hosted, and still built around real radio use.

Linux is still the strongest target and the most natural fit for attached radios and cyberdeck-style use, but the install path is also being cleaned up so OverMesh is easier to run natively on Windows and macOS.

## Highlights

Cross-system work is now real and usable. OverMesh can mirror traffic one way between MT and MC, or bridge it both ways. Rules can be saved, filtered by sender, and clearly tagged so forwarded traffic does not look like a normal local message.

MeshCore is no longer treated like a secondary panel on an MT app. It now has proper chat tabs, DM tabs, delivery state, bot support, Sense activity, map and Nodes parity work, and better heard-recently logic that matches how MC actually behaves.

Meshtastic and MeshCore now feel much closer as one product. A long consistency sweep cleaned up labels, map actions, contact and node handling, unread indicators, notifications, and a lot of the small UI mismatches that made the app feel uneven before.

## New and improved

MC bot support was expanded, including better channel-scoped replies, so a bot response stays where it belongs instead of leaking into every MC channel view.

In-app notifications were added for new messages, new nodes, and nodes seen again after a long gap, with settings toggles and calmer styling so they stay useful instead of noisy.

Per-channel history cleanup is now available in Settings on both sides, so MT and MC channel history can be cleared without wiping unrelated data.

Cross-system forwarding gained recent message dedupe, clearer tagging, saved rule editing, per-rule enable and disable, better target matching for direct commands, and a cleaner rule layout.

MC map and Sense behavior was tightened up, including node list jumps from map popups, more consistent last seen handling, and better live updates from pings and activity.

Message metadata got cleaner too. MT messages now show time without repeating the date on every line, and both systems can show SNR in the message meta when it is available, with MC treated as observed data rather than guaranteed packet metadata.

## Current shape

Mirror means one-way monitoring or copying from one system to the other.

Bridge means a two-way linked path between one MT channel and one MC channel.

Every forwarded message is clearly marked with the source system, original sender, and source channel, so relayed traffic does not pretend to be native local traffic.

## Still not in scope

DM bridging is not implemented yet.

Cross system forwarding is still channel to channel, not arbitrary message routing.

Some MC metadata is still best effort, especially where MeshCore does not expose the same packet detail as Meshtastic.
