"""Normalize Fleet select values and consolidate legacy Vehicle attachments."""


def execute():
    import frappe

    transport_option_migrations = {
        "transport_kind": {
            "Transport collectif de personnes": "Collective Passenger Transport",
            "Transport scolaire": "School Transport",
            "Transport de marchandises": "Goods Transport",
            "Transport de matières dangereuses": "Dangerous Goods Transport",
            "Transport par taxi": "Taxi Transport",
        },
        "transport_basis": {
            "Compte d'autrui": "For-Hire Transport",
            "Compte propre": "Own-Account Transport",
        },
        "transport_regulatory_status": {
            "À confirmer": "To Be Confirmed",
            "Réglementé": "Regulated",
            "Non soumis (confirmation officielle)": "Officially Confirmed Not Subject",
        },
    }

    if frappe.db.table_exists("Operational Task"):
        for fieldname, values in transport_option_migrations.items():
            for old_value, new_value in values.items():
                names = frappe.get_all(
                    "Operational Task",
                    filters={fieldname: old_value},
                    pluck="name",
                    limit_page_length=0,
                )
                for name in names:
                    frappe.db.set_value(
                        "Operational Task",
                        name,
                        fieldname,
                        new_value,
                        update_modified=False,
                    )

    if frappe.db.table_exists("Company Classification"):
        classification_categories = {
            "TP (Travaux Publics)": "Public Works (TP)",
            "BTP (Bâtiment et Travaux Publics)": "Building and Public Works (BTP)",
            "Hydraulique": "Hydraulics",
            "Forestier": "Forestry",
        }
        for old_value, new_value in classification_categories.items():
            names = frappe.get_all(
                "Company Classification",
                filters={"category": old_value},
                pluck="name",
                limit_page_length=0,
            )
            for name in names:
                frappe.db.set_value(
                    "Company Classification",
                    name,
                    "category",
                    new_value,
                    update_modified=False,
                )

    if not frappe.db.table_exists("Vehicle"):
        return

    vehicle_category_migrations = {
        "Grader": "Motor Grader",
        "Roller": "Road Roller",
        "Paver": "Asphalt Paver",
    }
    for old_value, new_value in vehicle_category_migrations.items():
        names = frappe.get_all(
            "Vehicle",
            filters={"vehicle_category": old_value},
            pluck="name",
            limit_page_length=0,
        )
        for name in names:
            frappe.db.set_value(
                "Vehicle",
                name,
                "vehicle_category",
                new_value,
                update_modified=False,
            )

    if not frappe.db.table_exists("Vehicle Document"):
        frappe.clear_cache(doctype="Vehicle")
        return

    document_type_migrations = {
        "Carte d'immatriculation": "Registration Certificate",
        "Carte Grise (Registration)": "Registration Certificate",
        "Assurance (Insurance)": "Insurance Certificate",
        "Certificat de Pollution": "Other Document",
        "Visite Technique": "Technical Inspection",
        "Certificat de Conformité": "Certificate of Conformity",
        "Permis de Circulation": "Transport Permit",
        "Vignette": "Vehicle Tax Sticker",
        "Autre": "Other Document",
    }
    for old_value, new_value in document_type_migrations.items():
        rows = frappe.get_all(
            "Vehicle Document",
            filters={"document_type": old_value},
            pluck="name",
            limit_page_length=0,
        )
        for name in rows:
            frappe.db.set_value(
                "Vehicle Document",
                name,
                "document_type",
                new_value,
                update_modified=False,
            )

    legacy_attachments = {
        "registration_document": "Registration Certificate",
        "insurance_document": "Insurance Certificate",
        # Pollution Under Control is not an Algerian vehicle document type;
        # preserve the uploaded file under the neutral Other Document category.
        "pollution_document": "Other Document",
        "technical_document": "Technical Inspection",
    }
    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", *legacy_attachments],
        limit_page_length=0,
    )
    for vehicle in vehicles:
        existing_rows = frappe.get_all(
            "Vehicle Document",
            filters={
                "parent": vehicle.name,
                "parenttype": "Vehicle",
                "parentfield": "vehicle_documents",
            },
            fields=["name", "attachment", "document_type", "idx"],
            limit_page_length=0,
        )
        existing_document_pairs = {
            (row.attachment, row.document_type)
            for row in existing_rows
            if row.attachment
        }
        next_idx = max((row.idx or 0 for row in existing_rows), default=0) + 1

        for fieldname, document_type in legacy_attachments.items():
            attachment = vehicle.get(fieldname)
            document_pair = (attachment, document_type)
            if not attachment or document_pair in existing_document_pairs:
                continue

            row = frappe.get_doc(
                {
                    "doctype": "Vehicle Document",
                    "parent": vehicle.name,
                    "parenttype": "Vehicle",
                    "parentfield": "vehicle_documents",
                    "idx": next_idx,
                    "document_type": document_type,
                    "attachment": attachment,
                    "status": "Pending",
                }
            )
            # Insert the child row directly so historical submitted Vehicles
            # remain untouched by document validation or submit-state rules.
            row.db_insert()
            existing_document_pairs.add(document_pair)
            next_idx += 1

    frappe.clear_cache(doctype="Operational Task")
    frappe.clear_cache(doctype="Company Classification")
    frappe.clear_cache(doctype="Vehicle")
    frappe.clear_cache(doctype="Vehicle Document")
