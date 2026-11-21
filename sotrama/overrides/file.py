"""File download permissions for HR-only Driver attachments."""

import frappe


class DriverPrivateFileMixin:
    def is_downloadable(self):
        from sotrama.permissions import (
            can_access_driver_private_attachment,
            is_driver_private_attachment,
        )

        if is_driver_private_attachment(
            self
        ) and not can_access_driver_private_attachment(self, frappe.session.user):
            return False

        return super().is_downloadable()
