// White circle over the LG G8x in-display sensor while the screen is locked.
// Sensor centre and radius in panel pixels (LineageOS config_udfps_sensor_props: 540, 2107, r 98; drawn a bit larger).
import St from 'gi://St';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const CX = 540, CY = 2107, R = 110, PW = 1080, PH = 2340;

export default class G8xFingerprintSpot extends Extension {
    enable() {
        this._spot = new St.Widget({style: 'background-color: white;', reactive: false, visible: false});
        Main.layoutManager.addTopChrome(this._spot, {trackFullscreen: false});
        this._om = global.backend.get_orientation_manager();
        this._place();
        this._monId = Main.layoutManager.connect('monitors-changed', () => this._place());
        this._orId = this._om.connect('orientation-changed', () => this._place());
        this._modeId = Main.sessionMode.connect('updated', () => this._sync());
        this._sync();
    }

    _place() {
        const m = Main.layoutManager.primaryMonitor;
        if (!m)
            return;
        const s = m.geometry_scale || 1;
        const r = Math.round(R / s);
        // sensor position in the current screen orientation (panel pixels); a portrait-shaped monitor is NORMAL
        let [x, y] = [CX, CY];
        if (m.width > m.height) {
            const o = this._om.get_orientation();
            if (o === Meta.Orientation.RIGHT_UP)
                [x, y] = [CY, PW - CX];
            else
                [x, y] = [PH - CY, CX];          // LEFT_UP (and unknown landscape)
        } else if (this._om.get_orientation() === Meta.Orientation.BOTTOM_UP) {
            [x, y] = [PW - CX, PH - CY];
        }
        this._spot.set_position(m.x + Math.round(x / s) - r, m.y + Math.round(y / s) - r);
        this._spot.set_size(2 * r, 2 * r);
        this._spot.set_style(`background-color: white; border-radius: ${r}px;`);
    }

    _sync() {
        this._spot.visible = Main.sessionMode.isLocked;
        if (this._spot.visible)
            Main.layoutManager.uiGroup.set_child_above_sibling(this._spot, null);
    }

    disable() {
        Main.layoutManager.disconnect(this._monId);
        this._om.disconnect(this._orId);
        Main.sessionMode.disconnect(this._modeId);
        this._spot.destroy();
        this._spot = null;
    }
}
