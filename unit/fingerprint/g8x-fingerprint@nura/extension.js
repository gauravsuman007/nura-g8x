// LG G8x in-display fingerprint UI for GNOME Shell (mobile).
//
// Talks to egistad over the /run/egistad-ui.sock socket ("WAIT <service>\t<reason>", "RETRY", "MATCH", "NOMATCH", "IDLE",
// "PROGRESS <pct>"; we answer "SHOW 1/0" and "CANCEL"). egistad only starts a capture while we report the circle as
// shown, so a touch on the PIN pad or the keyboard over the sensor never lights the spot.
//
// Lock screen: either fingerprint mode (clock + circle + "Use PIN") or PIN mode (pad + "Use fingerprint"), never both.
// Waking the screen always starts in fingerprint mode. Anything else that wants a finger (sudo, admin dialogs,
// enrolling) gets a card with the reason and "Use password", above the on-screen keyboard; when the phone panel is dark
// (docked) it is woken for the scan and the card is also shown on the other monitors.
// The lock screen and the admin (polkit) dialog grab input, so everything is drawn in one layer that is moved into
// whichever of them is up (outside the grab it could not be touched, and a touch on the circle would reach the lock
// screen and open the PIN pad).
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Meta from 'gi://Meta';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as AuthPrompt from 'resource:///org/gnome/shell/gdm/authPrompt.js';
import * as GdmUtil from 'resource:///org/gnome/shell/gdm/util.js';

// Sensor centre and radius in panel pixels (LineageOS config_udfps_sensor_props: 540, 2107, r 98; drawn a bit larger).
const CX = 540, CY = 2107, R = 110, PW = 1080, PH = 2340;
const UI_SOCK = '/run/egistad-ui.sock';
// capture dim layer: ~60 % dark, tinted towards magenta to cancel the HBM gamma's green
const DIM_COLOR = 'rgba(28,0,24,0.6)';
const TWEAKS_CONF = '/etc/nura/tweaks.conf';   // FP_CUSTOM=0 (LG G8x Tweaks): stock GNOME only, this UI stays off
const BL_POWER = '/sys/class/backlight/r66456-bl/bl_power';

const CARD_STYLE = 'background-color: rgba(30,30,30,0.96); border-radius: 24px; padding: 18px 22px; ' +
    'color: white; spacing: 10px;';
const BUTTON_STYLE = 'background-color: rgba(255,255,255,0.14); border-radius: 18px; padding: 8px 20px; ' +
    'color: white; font-weight: bold;';

function stop() {
    return Clutter.EVENT_STOP;
}

function customWanted() {
    try {
        const [, bytes] = GLib.file_get_contents(TWEAKS_CONF);
        return !/^\s*FP_CUSTOM=0/m.test(new TextDecoder().decode(bytes));
    } catch {
        return true;
    }
}

export default class G8xFingerprint extends Extension {
    // The tweaks setting is watched so the switch applies without a restart. Off: no socket, no overlay, no
    // injection, so egistad (with no UI connected) captures on its own and GNOME's own fingerprint prompt is all there is.
    enable() {
        this._running = false;
        this._confMon = Gio.File.new_for_path(TWEAKS_CONF).monitor_file(Gio.FileMonitorFlags.NONE, null);
        this._confMon.connect('changed', () => this._applyConf());
        this._applyConf();
    }

    disable() {
        this._confMon?.cancel();
        this._confMon = null;
        if (this._running)
            this._stop();
        this._running = false;
    }

    _applyConf() {
        const want = customWanted();
        if (want === this._running)
            return;
        this._running = want;
        if (want)
            this._start();
        else
            this._stop();
    }

    _start() {
        this._waiting = null;        // [service, reason] while egistad wants a finger
        this._shown = false;
        this._feedback = '';
        this._om = global.backend.get_orientation_manager();
        this._mm = global.backend.get_monitor_manager();

        this._layer = null;          // built per host (see _placeLayer)
        this._host = null;

        // the same message on the other monitors while docked with the phone panel dark
        this._remote = [];

        this._ids = [
            [Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => this._sync())],
            [this._om, this._om.connect('orientation-changed', () => this._sync())],
            [Main.sessionMode, Main.sessionMode.connect('updated', () => this._onSessionMode())],
            [this._mm, this._mm.connect('power-save-mode-changed', () => this._onPowerSave())],
        ];
        // GNOME runs gdm-fingerprint beside the PIN and hints "(or place finger on reader)" under it; in our PIN mode
        // the sensor is off, so drop that hint there (official extension API, undone on disable)
        this._injections = new InjectionManager();
        const self = this;
        this._injections.overrideMethod(AuthPrompt.AuthPrompt.prototype, 'setMessage', orig => function (message, type, ...rest) {
            if (type === GdmUtil.MessageType.HINT && self._lockDialog())
                message = null;
            return orig.call(this, message, type, ...rest);
        });
        this._connect();
        this._onSessionMode();
    }

    _stop() {
        this._injections?.clear();
        this._injections = null;
        for (const [o, id] of this._ids)
            o.disconnect(id);
        this._ids = [];
        if (this._reconnectId)
            GLib.source_remove(this._reconnectId);
        this._reconnectId = 0;
        this._cancellable?.cancel();
        try {
            this._conn?.close(null);
        } catch {}
        this._conn = null;
        if (this._hooked?._clickGesture)
            this._hooked._clickGesture.enabled = true;
        this._unhookLock();
        this._restorePanel();
        this._clearRemote();
        this._dropLayer();
    }

    // ---- egistad UI socket
    _connect() {
        this._cancellable = new Gio.Cancellable();
        const client = new Gio.SocketClient();
        client.connect_async(Gio.UnixSocketAddress.new(UI_SOCK), this._cancellable, (c, res) => {
            try {
                this._conn = c.connect_finish(res);
            } catch {
                this._retry();
                return;
            }
            this._out = this._conn.get_output_stream();
            this._in = new Gio.DataInputStream({base_stream: this._conn.get_input_stream()});
            this._sentShown = null;
            this._readLine();
            this._sync();
        });
    }

    _retry() {
        this._conn = null;
        this._waiting = null;
        this._sync();
        if (!this._reconnectId) {
            this._reconnectId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {
                this._reconnectId = 0;
                this._connect();
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    _readLine() {
        this._in.read_line_async(GLib.PRIORITY_DEFAULT, this._cancellable, (s, res) => {
            let line;
            try {
                [line] = s.read_line_finish_utf8(res);
            } catch {
                line = null;
            }
            if (line === null) {
                this._retry();
                return;
            }
            this._onLine(line);
            this._readLine();
        });
    }

    _write(line) {
        if (!this._out)
            return;
        try {
            this._out.write_all(new TextEncoder().encode(`${line}\n`), null);
        } catch {}
    }

    _onLine(line) {
        if (line.startsWith('WAIT ')) {
            this._touching = false;
            const [svc, reason] = line.slice(5).split('\t');
            this._waiting = [svc, reason || ''];
            this._feedback = '';
            this._wakePanelIfDark();
        } else if (line === 'DOWN') {
            this._touching = true;
        } else if (line === 'UP') {
            this._touching = false;
        } else if (line === 'IDLE') {
            this._waiting = null;
            this._touching = false;
            this._feedback = '';
            this._restorePanel();
        } else if (line === 'NOMATCH') {
            this._touching = false;
            this._feedback = 'Not recognised. Try again.';
        } else if (line === 'RETRY') {
            this._feedback = 'Hold your finger still on the circle';
        } else if (line.startsWith('PROGRESS ')) {
            this._feedback = `${line.slice(9)}% - lift and touch again`;
        } else if (line === 'MATCH') {
            this._touching = false;
            this._feedback = '';
        }
        this._sync();
    }

    // ---- lock screen
    _onSessionMode() {
        this._touching = false;
        if (Main.sessionMode.isLocked)
            this._hookLock();
        else
            this._unhookLock();
        this._sync();
    }

    _lockDialog() {
        return Main.sessionMode.isLocked ? Main.screenShield?._dialog ?? null : null;
    }

    _hookLock() {
        const d = this._lockDialog();
        if (!d || this._hooked === d)
            return;
        this._unhookLock();
        this._hooked = d;
        // PIN pad slides in and out with translation-y: follow it
        this._promptId = d._promptBox.connect('notify::translation-y', () => this._sync());
        const row = new St.BoxLayout({style: 'spacing: 8px;'});
        row.add_child(new St.Icon({icon_name: 'fingerprint-detection-symbolic', icon_size: 18}));
        row.add_child(new St.Label({text: 'Use fingerprint', y_align: Clutter.ActorAlign.CENTER}));
        this._fpButton = new St.Button({
            style: BUTTON_STYLE, x_align: Clutter.ActorAlign.CENTER, can_focus: true, child: row,
        });
        this._fpButton.connect('clicked', () => this._showFingerprintMode());
        d._promptBox.insert_child_at_index(this._fpButton, 0);
        if (this._waiting)
            this._showFingerprintMode();
    }

    _unhookLock() {
        if (this._hooked) {
            const pb = this._hooked._promptBox;
            try {
                if (pb && this._promptId && GObject.signal_handler_is_connected(pb, this._promptId))
                    pb.disconnect(this._promptId);
            } catch {}
            try {
                this._fpButton?.destroy();
            } catch {}
        }
        this._promptId = 0;
        this._hooked = null;
        this._fpButton = null;
    }

    _pinShown(d) {
        const h = d._promptBoxHeight || d._promptBox.height || 1;
        return d._promptBox.translation_y < h / 2;
    }

    _showFingerprintMode() {
        const d = this._lockDialog();
        if (!d)
            return;
        d._authPrompt?.clear?.();
        d._showClock();
        this._sync();
    }

    _onPowerSave() {
        this._touching = false;
        // screen just came on while locked: start with the fingerprint, not the PIN pad
        if (this._mm.power_save_mode === 0 && this._lockDialog() && this._waiting)
            this._showFingerprintMode();
        this._sync();
    }

    _onButton() {
        const d = this._lockDialog();
        if (d && this._isUnlock()) {
            d._showPrompt();             // PIN pad; fingerprint keeps listening in the background but the circle is off
        } else {
            this._write('CANCEL');       // sudo/polkit fall back to the password
        }
        this._sync();
    }

    _isUnlock() {
        return Main.sessionMode.isLocked;
    }

    // ---- phone panel while docked
    _builtinIndex() {
        let i = -1;
        try {
            i = this._mm.get_monitor_for_connector('DSI-1');
        } catch {}
        return i >= 0 ? i : Main.layoutManager.primaryIndex;
    }

    _panelDark() {
        let bl = '0';
        try {
            bl = new TextDecoder().decode(GLib.file_get_contents(BL_POWER)[1]).trim();
        } catch {}
        return this._mm.power_save_mode !== 0 || bl !== '0';
    }

    _wakePanelIfDark() {
        if (Main.sessionMode.isLocked || !this._panelDark())
            return;
        try {
            this._savedBl = new TextDecoder().decode(GLib.file_get_contents(BL_POWER)[1]).trim();
        } catch {
            this._savedBl = null;
        }
        if (this._mm.power_save_mode !== 0) {
            Gio.DBus.session.call('org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig',
                'org.freedesktop.DBus.Properties', 'Set',
                new GLib.Variant('(ssv)', ['org.gnome.Mutter.DisplayConfig', 'PowerSaveMode', new GLib.Variant('i', 0)]),
                null, Gio.DBusCallFlags.NONE, -1, null, null);
        }
        if (this._savedBl && this._savedBl !== '0')
            this._writeBl('0');
        this._woke = true;
    }

    _restorePanel() {
        if (!this._woke)
            return;
        this._woke = false;
        if (this._savedBl && this._savedBl !== '0')
            this._writeBl(this._savedBl);
        this._savedBl = null;
    }

    _writeBl(v) {
        try {
            GLib.spawn_async(null, ['/bin/sh', '-c', `echo ${v} > ${BL_POWER}`], null, GLib.SpawnFlags.DEFAULT, null);
        } catch {}
    }

    _clearRemote() {
        for (const a of this._remote)
            a.destroy();
        this._remote = [];
    }

    // ---- layout
    _sensorRect() {
        const idx = this._builtinIndex();
        const m = Main.layoutManager.monitors[idx];
        if (!m)
            return null;
        const s = m.geometry_scale || 1;
        const r = Math.round(R / s);
        // sensor position in the current screen orientation (panel pixels); a portrait-shaped monitor is NORMAL
        let [x, y] = [CX, CY];
        let landscape = false;
        if (m.width > m.height) {
            landscape = true;
            const o = this._om.get_orientation();
            if (o === Meta.Orientation.RIGHT_UP)
                [x, y] = [CY, PW - CX];
            else
                [x, y] = [PH - CY, CX];          // LEFT_UP (and unknown landscape)
        } else if (this._om.get_orientation() === Meta.Orientation.BOTTOM_UP) {
            [x, y] = [PW - CX, PH - CY];
        }
        return {m, idx, r, x: m.x + Math.round(x / s), y: m.y + Math.round(y / s), landscape};
    }

    _polkitDialog() {
        try {
            return Main.componentManager._allComponents?.polkitAgent?._currentDialog ?? null;
        } catch {
            return null;
        }
    }

    // Move the layer into the actor that holds the input grab (lock screen, polkit dialog) or onto the UI group.
    // Returns the stage offset of the host, to convert stage coordinates to layer coordinates.
    _buildLayer() {
        this._layer = new St.Widget({layout_manager: new Clutter.FixedLayout(), reactive: false});
        // black panel behind the whole request (outside the lock screen): nothing bright around the circle
        this._backdrop = new St.Widget({reactive: true, visible: false, style: 'background-color: black; border-radius: 28px;'});
        this._layer.add_child(this._backdrop);
        // dimming of the rest of the phone panel during a capture: the spot's HBM gamma briefly brightens the whole
        // panel and tints it green (it has no spot-only HBM). A dark layer with a little magenta (green's complement)
        // evens out both without blanking the screen.
        this._dim = new St.Widget({reactive: false, visible: false, style: `background-color: ${DIM_COLOR};`});
        this._layer.add_child(this._dim);
        // the circle: reactive so a touch on it never reaches what is underneath (lock-screen tap, keyboard keys)
        this._ring = new St.Widget({reactive: true, visible: false});
        this._spot = new St.Widget({reactive: true, visible: false});
        for (const a of [this._ring, this._spot]) {
            a.connect('touch-event', (_a, ev) => this._onSpotTouch(ev.type()));
            a.connect('button-press-event', () => this._onSpotTouch(Clutter.EventType.TOUCH_BEGIN));
            a.connect('button-release-event', () => this._onSpotTouch(Clutter.EventType.TOUCH_END));
            this._layer.add_child(a);
        }
        // text and button above the circle (lock-screen hint, or the request card)
        this._card = new St.BoxLayout({vertical: true, reactive: true, visible: false, style: CARD_STYLE});
        this._title = new St.Label({style: 'font-weight: bold; font-size: 13pt; text-align: center;'});
        this._reason = new St.Label({style: 'font-size: 11pt; text-align: center;'});
        this._reason.clutter_text.line_wrap = true;
        this._button = new St.Button({style: BUTTON_STYLE, x_align: Clutter.ActorAlign.CENTER, can_focus: true});
        this._button.connect('clicked', () => this._onButton());
        this._card.add_child(this._title);
        this._card.add_child(this._reason);
        this._card.add_child(this._button);
        this._layer.add_child(this._card);
        this._remote = [];
    }

    _dropLayer() {
        if (this._host && this._hostDestroyId) {
            try {
                this._host.disconnect(this._hostDestroyId);
            } catch {}
        }
        this._hostDestroyId = 0;
        this._layer?.destroy();
        this._layer = this._spot = this._ring = this._card = this._backdrop = this._dim = null;
        this._remote = [];
        this._host = null;
    }

    // Lock screen: the black ring only while a finger is on the circle, so the clock page stays visible otherwise.
    _onSpotTouch(type) {
        if (type === Clutter.EventType.TOUCH_BEGIN) {
            if (this._touchOffId)
                GLib.source_remove(this._touchOffId);
            this._touchOffId = 0;
            this._touching = true;
            this._sync();
        }
        if (type === Clutter.EventType.TOUCH_END || type === Clutter.EventType.TOUCH_CANCEL ||
            type === Clutter.EventType.TOUCH_BEGIN) {
            // lift normally arrives from egistad ("UP"); never leave the ring on if that is missed
            if (this._touchOffId)
                GLib.source_remove(this._touchOffId);
            {
                this._touchOffId = GLib.timeout_add(GLib.PRIORITY_DEFAULT,
                    type === Clutter.EventType.TOUCH_BEGIN ? 8000 : 400, () => {
                    this._touchOffId = 0;
                    this._touching = false;
                    this._sync();
                    return GLib.SOURCE_REMOVE;
                });
            }
        }
        return Clutter.EVENT_STOP;
    }

    _placeLayer(lockDialog) {
        const host = lockDialog ?? this._polkitDialog() ?? Main.layoutManager.uiGroup;
        if (host !== this._host || !this._layer) {
            this._dropLayer();
            this._buildLayer();
            this._host = host;
            host.add_child(this._layer);
            // the lock screen and the polkit dialog are destroyed when done, taking the layer with them
            this._hostDestroyId = host.connect('destroy', () => {
                this._layer = this._spot = this._ring = this._card = this._backdrop = this._dim = null;
                this._remote = [];
                this._host = null;
                this._hostDestroyId = 0;
                GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
                    this._sync();
                    return GLib.SOURCE_REMOVE;
                });
            });
        }
        const [ox, oy] = host === Main.layoutManager.uiGroup ? [0, 0] : host.get_transformed_position();
        this._layer.set_position(0, 0);
        return [Math.round(ox) || 0, Math.round(oy) || 0];
    }

    _sync() {
        if (!this._ids?.length)
            return;
        if (Main.sessionMode.isLocked)
            this._hookLock();
        const g = this._sensorRect();
        const d = this._lockDialog();
        const [ox, oy] = this._placeLayer(d);
        let showSpot = false, showCard = false;
        let title = '', reason = '', button = '';

        if (this._waiting && g) {
            const [svc, why] = this._waiting;
            if (d) {
                // lock screen: fingerprint mode only while the PIN pad is down
                showSpot = !this._pinShown(d);
                // a tap on the clock page would open the PIN pad: only "Use PIN" or a swipe up do that now
                if (d._clickGesture)
                    d._clickGesture.enabled = !showSpot;
                showCard = showSpot;
                title = this._feedback || 'Touch the sensor to unlock';
                reason = '';
                button = 'Use PIN';
            } else {
                showSpot = showCard = true;
                const pk = this._polkitDialog();
                const why2 = svc === 'polkit-1' && pk?.message ? pk.message : why;
                title = svc === 'enroll' ? 'Add fingerprint' : 'Fingerprint requested';
                reason = this._feedback ? `${why2}\n${this._feedback}` : why2;
                button = svc === 'enroll' ? 'Cancel' : 'Use password';
            }
        }
        if (d && !this._waiting && d._clickGesture && !this._pinShown(d))
            d._clickGesture.enabled = true;
        if (this._fpButton)
            this._fpButton.visible = Boolean(this._waiting) && Boolean(d) && this._pinShown(d);

        // circle, inside a black ring: the optical sensor also sees light from pixels next to the spot, and the
        // calibration was made with darkness around it (a bright terminal or keyboard there gave unusable images)
        // On the lock screen the ring appears only while touched (egistad waits for it before the first image).
        const ring = g ? g.r : 0;
        if (showSpot) {
            const o = g.r + ring;
            // the ring disc is always there to catch touches; it is only painted black when needed
            // black ring while a finger is on the circle (always outside the lock screen)
            const ringColor = !d || this._touching ? 'black' : 'rgba(0,0,0,0)';
            this._ring.set_position(g.x - o - ox, g.y - o - oy);
            this._ring.set_size(2 * o, 2 * o);
            this._ring.set_style(`background-color: ${ringColor}; border-radius: ${o}px;`);
            this._spot.set_position(g.x - g.r - ox, g.y - g.r - oy);
            this._spot.set_size(2 * g.r, 2 * g.r);
            this._spot.set_style(`background-color: white; border-radius: ${g.r}px;`);
        }
        this._ring.visible = showSpot;
        this._spot.visible = showSpot;
        this._dim.visible = showSpot && Boolean(this._touching);
        if (this._dim.visible) {
            this._dim.set_position(g.m.x - ox, g.m.y - oy);
            this._dim.set_size(g.m.width, g.m.height);
            this._layer.set_child_above_sibling(this._dim, null);
        }
        if (showSpot) {
            this._layer.set_child_above_sibling(this._ring, null);
            this._layer.set_child_above_sibling(this._spot, null);
        }

        // card above the circle (beside it in landscape)
        if (showCard) {
            this._title.text = title;
            this._reason.text = reason;
            this._reason.visible = reason !== '';
            this._button.label = button;
            const w = Math.min(g.m.width - 32, 360);
            this._card.set_width(w);
            const [, ch] = this._card.get_preferred_height(w);
            let cx = Math.round(g.x - w / 2), cy = g.y - g.r - ring - 12 - ch;
            if (g.landscape) {
                cx = g.x < g.m.x + g.m.width / 2 ? g.x + g.r + ring + 12 : g.x - g.r - ring - 12 - w;
                cy = Math.round(g.y - ch / 2);
            }
            cx = Math.max(g.m.x + 16, Math.min(cx, g.m.x + g.m.width - w - 16));
            cy = Math.max(g.m.y + 16, cy);
            this._card.set_position(cx - ox, cy - oy);
        }
        this._card.visible = showCard;

        // outside the lock screen the card and circle sit on one black panel reaching the screen edge
        const panel = showCard && !d;
        if (panel) {
            this._card.set_style(CARD_STYLE.replace('rgba(30,30,30,0.96)', 'black'));
            const [cx, cy] = this._card.get_position();
            const [cw] = this._card.get_size();
            const o = g.r + ring;
            let x1 = Math.min(cx, g.x - o - ox) - 12, x2 = Math.max(cx + cw, g.x + o - ox) + 12;
            let y1 = Math.min(cy, g.y - o - oy) - 12, y2 = Math.max(g.y + o - oy, cy + this._card.height) + 12;
            const mx1 = g.m.x - ox, my1 = g.m.y - oy, mx2 = mx1 + g.m.width, my2 = my1 + g.m.height;
            // run to the nearest monitor edge beyond the circle (bottom in portrait, side in landscape)
            if (g.landscape) {
                if (g.x - ox < (mx1 + mx2) / 2) x1 = mx1; else x2 = mx2;
            } else {
                y2 = my2;
                x1 = Math.max(mx1, x1); x2 = Math.min(mx2, x2);
            }
            this._backdrop.set_position(x1, y1);
            this._backdrop.set_size(x2 - x1, y2 - y1);
        } else if (showCard) {
            this._card.set_style(CARD_STYLE);
        }
        this._backdrop.visible = panel;

        // other monitors (docked): tell the user where to put the finger
        this._clearRemote();
        if (showSpot && !d) {
            Main.layoutManager.monitors.forEach((m, i) => {
                if (i === g.idx)
                    return;
                const box = new St.BoxLayout({vertical: true, reactive: true, style: CARD_STYLE});
                box.add_child(new St.Label({text: title, style: 'font-weight: bold; font-size: 13pt;'}));
                box.add_child(new St.Label({text: `${reason}\nTouch the fingerprint sensor on the phone screen.`}));
                const b = new St.Button({style: BUTTON_STYLE, label: button, x_align: Clutter.ActorAlign.CENTER});
                b.connect('clicked', () => this._onButton());
                box.add_child(b);
                this._layer.add_child(box);
                const [, nat] = box.get_preferred_width(-1);
                box.set_position(m.x + Math.round((m.width - nat) / 2) - ox, m.y + Math.round(m.height * 0.35) - oy);
                this._remote.push(box);
            });
        }

        // keep the layer on top of its host
        const p = this._layer.get_parent();
        if (p)
            p.set_child_above_sibling(this._layer, null);

        const shown = showSpot && Boolean(this._conn);
        if (shown !== this._sentShown) {
            this._sentShown = shown;
            this._write(`SHOW ${shown ? 1 : 0}`);
        }
    }
}
