# MC Server Soft — Home Assistant

HACS custom integration for MC Server Soft API v2.

### Included

- Dynamic server discovery
- Configurable data/console/player refresh intervals
- Server-icon camera
- Status, CPU, memory, player count
- Player-name list using the Minecraft `list` console command
- Numeric uptime plus automatically formatted uptime
- Recent console output and latest console line
- Start / Stop / Restart / Kill
- Per-server console command text entity
- `mcss.send_command` and `mcss.server_action` services

### API key

The integration references an existing Home Assistant `input_text` instead of storing a second copy of the key.

Example:

```yaml
input_text:
  mcss_apikey:
    name: MCSS API Key
    mode: password
    max: 200
```

Select `input_text.mcss_apikey` during setup.

### Uptime formatting

The `Uptime display` sensor produces:

`00:43:17`

then:

`1d 03:43:17`

then:

`2w 1d 03:43:17`

The numeric `Uptime` sensor remains seconds for automations.

### Player names

MCSS API v2 documents player count in server stats but does not document a player-name endpoint. The integration therefore issues the normal Minecraft `list` command and parses the standard Java response. Count remains available even when a server has a non-standard response.

### Console

`Latest console output` is the newest line. Its `lines` attribute contains the configured number of recent lines.

### Important

This release dynamically adds newly discovered servers. When MCSS removes a server, its existing HA entities become unavailable; they are not forcibly deleted from the entity registry, because HA entity-registry deletion at runtime is unsafe for a third-party integration.
