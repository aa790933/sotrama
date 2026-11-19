"""Non-invasive setup helpers for Sotrama and its ERPNext integration."""

PUBLIC_WORKS_DESIGNATIONS = (
    ("Agent administratif", "Administration et gestion"),
    ("Agent de liaison administrative", "Administration et gestion"),
    ("Agent de maintenance", "Maintenance et atelier"),
    ("Agent de sécurité", "Sécurité et prévention"),
    ("Agent d'entretien et de nettoyage", "Services généraux"),
    ("Agent de gardiennage", "Sécurité et prévention"),
    (
        "Agent d'hygiène, sécurité et environnement",
        "Hygiène, sécurité et environnement",
    ),
    ("Aide-comptable", "Comptabilité et finances"),
    ("Aide-mécanicien", "Maintenance et atelier"),
    ("Apprenti en formation professionnelle", "Formation professionnelle"),
    ("Automaticien", "Maintenance et automatisme"),
    ("Assistant administratif", "Administration et gestion"),
    (
        "Chargé d'affaires en bâtiment, travaux publics et hydraulique",
        "Conduite et gestion des travaux",
    ),
    (
        "Chargé du suivi des travaux en bâtiment, travaux publics et hydraulique",
        "Conduite et gestion des travaux",
    ),
    ("Chef de bureau", "Administration et gestion"),
    ("Chef de carrière", "Carrière et production"),
    ("Chef de centrale à béton", "Carrière et production"),
    ("Chef de chantier", "Conduite et gestion des travaux"),
    ("Chef de département informatique", "Informatique"),
    ("Chef d'entretien", "Maintenance et atelier"),
    ("Chef d'équipe", "Conduite et gestion des travaux"),
    ("Chef électrotechnicien", "Maintenance et atelier"),
    ("Chef mécanicien", "Maintenance et atelier"),
    ("Chef de parc", "Gestion du parc"),
    ("Chef de poste", "Production et exploitation"),
    ("Chef pompiste", "Carburants et exploitation"),
    ("Comptable", "Comptabilité et finances"),
    ("Conducteur de bulldozer", "Conduite d'engins de chantier"),
    ("Conducteur de chargeuse", "Conduite d'engins de chantier"),
    ("Conducteur de compacteur", "Conduite d'engins de chantier"),
    ("Conducteur de finisseur", "Conduite d'engins de chantier"),
    ("Conducteur de fraiseuse routière", "Conduite d'engins de chantier"),
    ("Conducteur de niveleuse", "Conduite d'engins de chantier"),
    ("Conducteur de pelle hydraulique", "Conduite d'engins de chantier"),
    ("Conducteur de perforatrice", "Conduite d'engins de chantier"),
    ("Conducteur de pompe à béton", "Conduite d'engins de chantier"),
    ("Conducteur de rétrochargeur", "Conduite d'engins de chantier"),
    ("Conducteur de tombereau", "Conduite d'engins de chantier"),
    ("Conducteur d'engins de chantier", "Conduite d'engins de chantier"),
    (
        "Conducteur d'engins de chantier toutes catégories",
        "Conduite d'engins de chantier",
    ),
    ("Conducteur de travaux", "Conduite et gestion des travaux"),
    ("Contrôleur électronicien", "Maintenance et atelier"),
    ("Coordinateur de travaux", "Conduite et gestion des travaux"),
    ("Agent de dispatching", "Transport et logistique"),
    ("Directeur technique", "Direction et encadrement"),
    ("Électricien", "Maintenance et atelier"),
    ("Électricien automobile", "Maintenance et atelier"),
    ("Électricien industriel", "Maintenance et atelier"),
    ("Électromécanicien", "Maintenance et atelier"),
    ("Ferrailleur", "Métiers du chantier"),
    ("Gérant", "Direction et encadrement"),
    ("Géotechnicien", "Études et laboratoire"),
    ("Gestionnaire de carrière", "Carrière et production"),
    ("Gestionnaire de parc", "Gestion du parc"),
    ("Grutier", "Conduite d'engins de chantier"),
    ("Ingénieur d'État en travaux publics", "Études et ingénierie"),
    ("Ingénieur en génie civil", "Études et ingénierie"),
    ("Ingénieur géotechnicien", "Études et ingénierie"),
    ("Ingénieur hydraulicien", "Études et ingénierie"),
    ("Ingénieur électronicien", "Études et ingénierie"),
    ("Ingénieur électrotechnicien", "Études et ingénierie"),
    ("Ingénieur mécanicien", "Études et ingénierie"),
    (
        "Ingénieur en hygiène, sécurité et environnement",
        "Hygiène, sécurité et environnement",
    ),
    ("Ingénieur en contrôle de la qualité industrielle", "Qualité et contrôle"),
    ("Ingénieur qualité en industrie", "Qualité et contrôle"),
    ("Ingénieur en travaux publics", "Études et ingénierie"),
    ("Informaticien chargé d'études", "Informatique"),
    ("Laborantin d'analyses industrielles", "Études et laboratoire"),
    ("Magasinier", "Magasin et approvisionnement"),
    ("Magasinier gestionnaire de stocks", "Magasin et approvisionnement"),
    ("Maçon", "Métiers du chantier"),
    ("Manœuvre de chantier", "Métiers du chantier"),
    ("Manœuvre polyvalent de chantier", "Métiers du chantier"),
    ("Mécanicien", "Maintenance et atelier"),
    ("Mécanicien automobile", "Maintenance et atelier"),
    ("Mécanicien d'entretien", "Maintenance et atelier"),
    ("Mécanicien d'engins de chantier", "Maintenance et atelier"),
    ("Mécanicien diéséliste", "Maintenance et atelier"),
    ("Opérateur de centrale à béton", "Carrière et production"),
    ("Opérateur d'épandeuse à bitume", "Production et exploitation"),
    ("Opérateur de machine", "Production et exploitation"),
    ("Opérateur de salle de commande", "Production et exploitation"),
    ("Opérateur polyvalent de production", "Production et exploitation"),
    ("Plombier", "Maintenance et atelier"),
    ("Pompiste", "Carburants et exploitation"),
    ("Responsable commercial", "Commerce et développement"),
    ("Sous-directeur", "Direction et encadrement"),
    ("Soudeur", "Maintenance et atelier"),
    ("Technicien", "Technique et maintenance"),
    (
        "Technicien en hygiène, sécurité et environnement",
        "Hygiène, sécurité et environnement",
    ),
    ("Technicien en maintenance automobile", "Maintenance et atelier"),
    ("Technicien supérieur en électromécanique", "Maintenance et atelier"),
    ("Technicien supérieur en topographie", "Études et laboratoire"),
    ("Technicien supérieur en travaux publics", "Études et ingénierie"),
    ("Topographe", "Études et laboratoire"),
    ("Chauffeur coursier", "Transport et logistique"),
    ("Chauffeur de direction", "Transport et logistique"),
    ("Chauffeur de camion benne", "Transport et logistique"),
    ("Chauffeur de camion", "Transport et logistique"),
    ("Chauffeur de camion épandeur", "Transport et logistique"),
    ("Chauffeur de pompe à béton", "Transport et logistique"),
    ("Chauffeur de transport de personnel", "Transport et logistique"),
    ("Chauffeur de transport routier", "Transport et logistique"),
    ("Chauffeur de véhicule léger", "Transport et logistique"),
    ("Chauffeur poids lourd", "Transport et logistique"),
    ("Chauffeur poids lourd semi-remorque", "Transport et logistique"),
)


def ensure_default_masters():
    """Create missing fleet reference records without overwriting site edits."""
    import frappe

    default_makes = (
        "Mercedes-Benz",
        "Volvo",
        "Scania",
        "Renault Trucks",
        "IVECO",
        "MAN",
        "Tata",
    )
    for make_name in default_makes:
        if not frappe.db.exists("Vehicle Make", {"make_name": make_name}):
            frappe.get_doc({"doctype": "Vehicle Make", "make_name": make_name}).insert(
                ignore_permissions=True
            )

    default_job_types = (
        ("Oil Change", "Engine", 1.0, 2500),
        ("Brake Service", "Braking", 2.0, 5000),
        ("Transmission Service", "Drive Line", 3.0, 7500),
        ("Tire Rotation", "Tyres", 0.5, 1500),
        ("Engine Tune-up", "Engine", 4.0, 10000),
        ("Electrical Check", "Electrical", 2.0, 4000),
        ("Suspension Service", "Suspension", 3.0, 6000),
        ("Annual Inspection", "Safety", 4.0, 8000),
    )
    for job_type_name, category, standard_hours, default_rate in default_job_types:
        if not frappe.db.exists(
            "Maintenance Job Type", {"job_type_name": job_type_name}
        ):
            frappe.get_doc(
                {
                    "doctype": "Maintenance Job Type",
                    "job_type_name": job_type_name,
                    "job_category": category,
                    "standard_labour_hours": standard_hours,
                    "default_rate": default_rate,
                }
            ).insert(ignore_permissions=True)


def ensure_public_works_designations():
    """Create missing Algerian BTPH job titles in Frappe HR's Designation master.

    This helper is called only after an administrator explicitly enables the
    option in Sotrama Settings. Existing Designation records are never changed
    or deleted; HR users continue managing them through the standard HRMS UI.
    """
    import frappe

    if not frappe.db.exists("DocType", "Designation"):
        frappe.throw(
            frappe._(
                "Frappe HR's Designation DocType is unavailable. Install or enable Frappe HR first."
            )
        )

    meta = frappe.get_meta("Designation")
    if not meta.has_field("designation_name"):
        frappe.throw(
            frappe._(
                "The installed Designation DocType does not expose the expected designation_name field."
            )
        )

    if not frappe.has_permission("Designation", "create"):
        frappe.throw(
            frappe._(
                "You need permission to create Designation records before adding the BTPH list."
            )
        )

    designation_names = [name for name, _category in PUBLIC_WORKS_DESIGNATIONS]
    existing_names = set(
        frappe.get_all(
            "Designation",
            filters={"designation_name": ["in", designation_names]},
            pluck="designation_name",
        )
    )

    created = []
    for designation_name, _category in PUBLIC_WORKS_DESIGNATIONS:
        if designation_name in existing_names:
            continue

        designation = frappe.new_doc("Designation")
        designation.designation_name = designation_name
        designation.insert()
        created.append(designation.name)

    return created


def setup(company, is_setup=True):
    """Keep regional setup non-invasive; Sotrama features require admin opt-in.

    ERPNext's standard regional setup remains authoritative for Company data.
    Optional Sotrama fields are enabled from Sotrama Settings after installation.
    """
