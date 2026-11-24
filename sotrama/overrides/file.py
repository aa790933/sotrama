"""File lifecycle and permission extensions for Fleet and Driver attachments."""

import frappe


class DriverPrivateFileMixin:
    """Apply Fleet privacy before storage and retain Driver-specific controls."""

    def before_insert(self):
        """Set privacy before File.before_insert stores or reuses uploaded bytes."""
        from sotrama.permissions import (
            DRIVER_FILE_PRIVACY_FIELD,
            FLEET_FILE_PRIVACY_FIELD,
            is_company_scoped_fleet_attachment,
            is_driver_private_attachment,
            prevent_fleet_attachment_content_reuse,
        )

        prevent_fleet_attachment_content_reuse(self)
        is_fleet_attachment = is_company_scoped_fleet_attachment(self)
        if is_fleet_attachment or is_driver_private_attachment(self):
            self.is_private = 1
        if is_fleet_attachment:
            setattr(self, FLEET_FILE_PRIVACY_FIELD, 1)
        if is_driver_private_attachment(self):
            setattr(self, DRIVER_FILE_PRIVACY_FIELD, 1)

        result = super().before_insert()
        # Frappe's copy_from_existing_file branch returns before save_file();
        # move a copied public blob explicitly before the new File is inserted.
        if is_fleet_attachment and (self.file_url or "").startswith("/files/"):
            self.handle_is_private_changed()
        return result

    def save_file(
        self,
        content=None,
        decode=False,
        ignore_existing_file_check=False,
        overwrite=False,
    ):
        from sotrama.permissions import prevent_fleet_attachment_content_reuse

        content_for_hash = content
        if content and decode:
            self.content = content
            self.decode = decode
            content_for_hash = self.get_content()
        prevent_fleet_attachment_content_reuse(self, content=content_for_hash)
        return super().save_file(
            content=content,
            decode=decode,
            ignore_existing_file_check=ignore_existing_file_check,
            overwrite=overwrite,
        )

    def after_insert(self):
        base_after_insert = getattr(super(), "after_insert", None)
        result = base_after_insert() if base_after_insert else None
        self._secure_fleet_duplicate_rows()
        return result

    def on_update(self):
        base_on_update = getattr(super(), "on_update", None)
        result = base_on_update() if base_on_update else None
        self._secure_fleet_duplicate_rows()
        return result

    def _secure_fleet_duplicate_rows(self):
        from sotrama.permissions import (
            is_direct_company_scoped_fleet_attachment,
            is_driver_private_attachment,
            secure_duplicate_fleet_file_rows,
        )

        if (
            is_direct_company_scoped_fleet_attachment(self)
            and not is_driver_private_attachment(self)
            and secure_duplicate_fleet_file_rows(self)
        ):
            stored_values = frappe.db.get_value(
                "File", self.name, ["file_url", "is_private"], as_dict=True
            )
            if stored_values:
                self.file_url = stored_values.file_url
                self.is_private = stored_values.is_private

    def is_downloadable(self):
        from sotrama.permissions import (
            can_access_company_scoped_fleet_attachment,
            can_access_driver_private_attachment,
            is_company_scoped_fleet_attachment,
            is_driver_private_attachment,
        )

        if is_driver_private_attachment(self):
            if not can_access_driver_private_attachment(self, frappe.session.user):
                return False
        elif is_company_scoped_fleet_attachment(self) and not (
            can_access_company_scoped_fleet_attachment(
                self, frappe.session.user, ptype="read"
            )
        ):
            # Frappe's File.has_permission grants an owner access before checking
            # the attached document. Do not let that shortcut bypass Company scope.
            return False

        return super().is_downloadable()
