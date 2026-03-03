# NetBox plugin configuration
# Loaded automatically by NetBox from /etc/netbox/config/

PLUGINS = [
    "netbox_topology_views",
    "netbox_custom_objects",
]

PLUGINS_CONFIG = {
    "netbox_topology_views": {
        # Show all device roles in the topology view by default
        "allow_coordinates_saving": True,
        "always_save_coordinates": True,
    },
}
