frappe.tour["Woocommerce Settings"] = {
	fr: [
		{
			"fieldname": "woocommerce_server_url",
			"description": "Adresse URL du serveur WooCommerce.<br>Ex. https://monsite.fr/"
		},
		{
			"fieldname": "enable_sync",
			"description": "Permet d'activer/désactiver la synchronisation"
		},
		{
			"fieldname": "last_synchronization_datetime",
			"description": "Dernière date de synchronisation.<br>Vous pouvez sélectionner une date dans le passé pour relancer une synchronisation."
		},
		{
			"fieldname": "last_synchronization_datetime",
			"description": "Dernière date de synchronisation"
		},
		{
			"tour_step_type": "Button",
			"button_label": __("Generate Secret"),
			"title": __("Generate Secret"),
			"description": "Génère une clé secrète de Webhook permettant d'authentifier les webhooks provenant de WooCommerce"
		},
		{
			"fieldname": "secret",
			"description": "Clé secrète de Webhook à ajouter dans vos Webhooks.<br>Dokos crée automatiquement des Webhook lors de l'enregistrement des paramètres."
		},
		{
			"fieldname": "api_consumer_key",
			"description": "Clé publique d'API à récupérer sur WooCommerce"
		},
		{
			"fieldname": "api_consumer_secret",
			"description": "Clé secrète d'API à récupérer sur WooCommerce"
		},
		{
			"fieldname": "endpoint",
			"description": "Point de terminaison pour configurer vos webhooks.<br>La configuration se fait automatiquement."
		},
		{
			"fieldname": "create_payments_and_sales_invoice",
			"description": "La facture et la paiement associés à la commande seront créés si les conditions sont réunies dans les informations fournies par WooCommerce.<br>Sinon Dokos ne créera qu'une commande client."
		},
		{
			"fieldname": "synchronize_stock_levels",
			"description": "Synchronise les niveaux de stock depuis Dokos vers WooCommerce.<br>La synchronisation est effectuée immédiatement lors de chaque mouvement stock dans Dokos et une fois par heure via une tâche planifiée."
		},
		{
			"fieldname": "synchronize_based_on",
			"description": "La synchronisation peut être basée sur la base des quantités projetées ou des quantités réelles. Les quantités projetées prennent en compte les commandes ou la production en cours."
		},
		{
			"fieldname": "woocommerce_site_timezone",
			"description": "Fuseau horaire de votre site WooCommerce.<br>Cette donnée sert à déterminer la date/heure de dernière synchronisation."
		},
		{
			"fieldname": "currency_precision",
			"description": "Nombre de décimales à prendre en compte lors de la synchronisation.<br>Cette valeur est utilisée pour mettre à jour les paramètres des champs de type <i>devise</i> dans les commandes client, factures de ventes et modèles de taxe et frais.",
			"next_step_tab": "defaults_section"
		},
		{
			"previous_step_tab": "general_details_tab",
			"fieldname": "warehouse",
			"description": "Entrepôt de référence pour la synchronisation des stocks et la création des commandes/factures/bons de livraison."
		},
		{
			"fieldname": "sales_order_series",
			"description": "Préfixe de série utilisé pour la création des commandes client."
		},
		{
			"fieldname": "price_list",
			"description": "Liste de prix utilisée pour la création des commandes client."
		},
		{
			"fieldname": "company",
			"description": "Société utilisée pour la création des commandes client."
		},
		{
			"fieldname": "cost_center",
			"description": "Centre de coûts utilisé pour la création des commandes client."
		},
		{
			"fieldname": "customer_group",
			"description": "Groupe de clients utilisé pour la création des clients."
		},
		{
			"fieldname": "delivery_after_days",
			"description": "Délai permettant de calculer la date de livraison renseignée dans les commandes client."
		},
		{
			"fieldname": "weight_unit",
			"description": "Unité de poids utilisé par défaut pour la création des commandes client."
		},
		{
			"fieldname": "default_uom",
			"description": "Unité de mesure utilisé par défaut pour la création des commandes client.",
			"next_step_tab": "sb_accounting_details"
		},
		{
			"previous_step_tab": "defaults_section",
			"fieldname": "get_tax_account",
			"description": "En cliquant sur ce bouton, Dokos récupérera la liste des comptes de taxe/TVA configurés sur WooCommerce.<br>Vous pourrez ensuite indiquer le compte comptable correspondant dans Dokos."
		},
		{
			"fieldname": "tax_accounts",
			"description": "Tableau de correspondance entre les identifiants de taxe/TVA dans WooCommerce et les comptes comptables à utiliser dans Dokos."
		},
		{
			"fieldname": "stripe_gateway",
			"description": "Passerelle de paiement Stripe configurée sur WooCommerce.<br>Permet de récupérer les informations à utiliser pour la comptabilisation des paiements Stripe dans Dokos, notamment le compte de frais Stripe et le centre de coûts associés à la passerelle de paiement.",
			"next_step_tab": "shipping_tab"
		},
		{
			"previous_step_tab": "sb_accounting_details",
			"fieldname": "get_shipping_methods",
			"description": "En cliquant sur ce bouton, Dokos récupérera la liste des méthodes de livraison configurées sur WooCommerce.<br>Vous pourrez ensuite indiquer le compte comptable correspondant dans Dokos."
		},
		{
			"fieldname": "shipping_accounts",
			"description": "Tableau de correspondance entre les identifiants de méthodes de livraison dans WooCommerce et les comptes comptables à utiliser dans Dokos."
		},
		{
			"fieldname": "fee_account",
			"description": "Compte de frais à utiliser pour les frais hors livraison.",
			"next_step_tab": "customers_tab"
		},
		{
			"previous_step_tab": "shipping_tab",
			"fieldname": "customer_groups_to_synchronize",
			"description": `
				Tableau permettant de lister les groupes de clients dans Dokos à synchroniser vers WooCommerce.<br>
				Tous les clients appartenant à ces groupes de clients seront synchronisés vers WooCommerce.<br>
				Le rôle WooCommerce correspondant lui sera attribué si l'option correspondante est cochée.`
		},
		{
			"fieldname": "synchronize_roles",
			"description": "Lors de la synchronisation des clients, le rôle WooCommerce correspondant à leur groupe de clients Dokos leur sera attribué.<br>Cette option nécessite un plugin de gestion des rôles particulier."
		},
		{
			"fieldname": "synchronize_vat_number",
			"description": "Si cette option est cochée, le numéro de TVA du client sera également synchronisé.<br>Peut nécessité un plugin particulier côté WooCommerce."
		},
		{
			"fieldname": "wp_api_username",
			"description": "Nom d'utilisateur WooCommerce à utiliser pour mettre à jour le rôle."
		},
		{
			"fieldname": "wp_application_password",
			"description": "Mot de passe d'application associé à l'utilisateur WooCommerce renseigné ci-dessus."
		},
	]
}