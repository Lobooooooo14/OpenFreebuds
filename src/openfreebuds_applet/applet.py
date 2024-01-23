import os
import signal

import pystrayx
from openfreebuds import event_bus
from openfreebuds.constants.events import EVENT_UI_UPDATE_REQUIRED, EVENT_DEVICE_PROP_CHANGED, \
    EVENT_MANAGER_STATE_CHANGED
from openfreebuds.device.generic.base import BaseDevice
from openfreebuds.logger import create_log
from openfreebuds.manager import FreebudsManager
from openfreebuds_applet import settings, utils
from openfreebuds_applet.dialog import first_run, device_select
from openfreebuds_applet.modules import device_autoconfig, ModuleManager
from openfreebuds_applet.ui import icons, tk_tools
from openfreebuds_applet.ui.base import QuitingMenu
from openfreebuds_applet.ui.menu_device import DeviceMenu
from openfreebuds_applet.ui.menu_no_device import DeviceOfflineMenu, DeviceScanMenu

log = create_log("Applet")


class FreebudsApplet:
    def __init__(self):
        super().__init__()
        self.started = False
        self.allow_ui_update = False
        self._on_device_available_called = False
        self.current_menu_hash = ""
        self.current_icon_hash = ""

        self.settings = settings.SettingsStorage()

        self.manager = FreebudsManager.get()
        self.manager.config.SAFE_RUN_WRAPPER = utils.safe_run_wrapper
        # self.manager.config.USE_SOCKET_SLEEP = self.settings.enable_sleep

        self.modules = ModuleManager(self.settings, self.manager)

        self.menu_offline = DeviceOfflineMenu(self)
        self.menu_scan = DeviceScanMenu(self)
        self.menu_device = DeviceMenu(self)

        self.tray_application = pystrayx.TrayApplication(name="OpenFreebuds",
                                                         title="OpenFreebuds",
                                                         icon=icons.generate_icon(1),
                                                         menu=pystrayx.Menu())

    @utils.with_ui_exception("MainThread")
    def start(self):
        icons.set_theme(self.settings.icon_theme)
        tk_tools.set_theme(self.settings.theme)

        log.info("Loading all modules...")
        self.modules.autostart()

        # self.enable_debug_logging()
        self._setup_ctrl_c()
        self._ui_update_loop()
        self.tray_application.run()

    def _setup_ctrl_c(self):
        # noinspection PyUnresolvedReferences,PyProtectedMember
        def _handle_ctrl_c(_, __):
            if not self.started:
                os._exit(1)
            log.debug("Leaving, press Ctrl-C again to force exit")
            self.exit()

        try:
            signal.signal(signal.SIGINT, _handle_ctrl_c)
        except ValueError:
            pass

    def exit(self):
        log.info("Exiting this app...")
        self.tray_application.menu = QuitingMenu()

        self.allow_ui_update = False
        self.started = False
        event_bus.invoke(EVENT_UI_UPDATE_REQUIRED)

    def update_icon(self):
        if not self.allow_ui_update:
            return

        # Fetch info
        mgr_state = self.manager.state
        if mgr_state == self.manager.STATE_CONNECTED:
            dev = self.manager.device  # type: BaseDevice

            noise_mode = dev.find_property("anc", "mode", 0)
            battery = dev.find_property("battery", "global", 0)
            if battery == 0:
                battery = 100
        else:
            battery = 0
            noise_mode = 0

        # Hashsum
        new_hash = icons.get_hash(mgr_state, battery, noise_mode)
        if self.current_icon_hash == new_hash:
            return

        # Title
        if mgr_state == self.manager.STATE_CONNECTED:
            title = f"{self.manager.device_name} | {battery}%"
        else:
            title = "OpenFreebuds"

        log.info(f"Change icon: {new_hash}")
        self.tray_application.icon = icons.generate_icon(mgr_state, battery, noise_mode)
        self.tray_application.title = title
        self.current_icon_hash = new_hash

    def apply_menu(self, menu):
        if not self.allow_ui_update:
            return

        items_hash = utils.items_hash_string(menu.items)
        if self.current_menu_hash != items_hash:
            self.current_menu_hash = items_hash
            self.tray_application.menu = menu

    @utils.async_with_ui("Applet")
    def _ui_update_loop(self):
        log.info("Started")
        timeout = 5 if self.settings.device_autoconfig else None

        self.started = True
        self.allow_ui_update = True

        event_queue = event_bus.register([
            EVENT_UI_UPDATE_REQUIRED,
            EVENT_DEVICE_PROP_CHANGED,
            EVENT_MANAGER_STATE_CHANGED
        ])

        if self.settings.address != "":
            log.info(f"Attach recently used device, mac={self.settings.address}")
            self.manager.set_device(self.settings.device_name, self.settings.address)
        elif not self.settings.device_autoconfig:
            log.info("No device and no autoconfig, show device picker...")
            device_select.start(self.settings, self.manager)

        if self.settings.first_run:
            first_run.show(self.settings, self.manager)

        while self.started:
            self.update_icon()
            if self.manager.state == self.manager.STATE_NO_DEV:
                self.apply_menu(self.menu_scan)
                device_autoconfig.process(self.manager, self.settings)
            elif self.manager.state == self.manager.STATE_CONNECTED:
                if not self._on_device_available_called:
                    self.on_device_available()
                    self._on_device_available_called = True
                self.apply_menu(self.menu_device)
            else:
                self.apply_menu(self.menu_offline)
                device_autoconfig.process(self.manager, self.settings)
            event_queue.wait(timeout)

        self.manager.close()
        self.tray_application.stop()
        log.info("Tray stopped, exiting...")

        # noinspection PyProtectedMember,PyUnresolvedReferences
        os._exit(0)

    def on_device_available(self):
        pass
