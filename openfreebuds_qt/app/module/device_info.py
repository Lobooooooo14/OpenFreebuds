from PyQt6.QtWidgets import QTableWidgetItem

from openfreebuds import OfbEventKind
from openfreebuds_qt.utils.core_event import OfbCoreEvent
from openfreebuds_qt.app.module.common import OfbQtCommonModule
from openfreebuds_qt.utils.qt_utils import qt_error_handler
from openfreebuds_qt.designer.device_info import Ui_OfbQtDeviceInfoModule


class OfbQtDeviceInfoModule(Ui_OfbQtDeviceInfoModule, OfbQtCommonModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setupUi(self)

    async def update_ui(self, event: OfbCoreEvent):
        async with qt_error_handler("OfbQtDeviceInfoModule_UpdateUi", self.ctx):
            if event.is_changed("info") or event.kind_match(OfbEventKind.DEVICE_CHANGED):
                device_name, device_address = await self.ofb.get_device_tags()
                info: dict[str, str] = await self.ofb.get_property("info")
                if info is None:
                    return

                self.device_address.setText(device_address)
                self.device_name.setText(device_name)
                self.device_firmware.setText(info.get("software_ver", "--"))

                self.all_data_table.clearContents()
                self.all_data_table.setRowCount(len(info.keys()))
                for index, (code, value) in enumerate(info.items()):
                    self.all_data_table.setItem(index, 0, QTableWidgetItem(code))
                    self.all_data_table.setItem(index, 1, QTableWidgetItem(value))
                self.all_data_table.show()
