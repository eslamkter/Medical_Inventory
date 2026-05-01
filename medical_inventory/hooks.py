import logging
import os
_logger = logging.getLogger(__name__)


def post_install_hook(env):
    _load_arabic(env)


def post_migrate_hook(env):
    _load_arabic(env)


def _load_arabic(env):
    try:
        ar_lang = env['res.lang'].search([('code', '=', 'ar_001'), ('active', '=', True)], limit=1)
        if not ar_lang:
            _logger.info("medical_inventory: Arabic not active, skip")
            return

        # Get path to our po file
        module_path = os.path.dirname(os.path.abspath(__file__))
        po_path = os.path.join(module_path, 'i18n', 'ar_001.po')

        if not os.path.exists(po_path):
            _logger.warning("medical_inventory: ar_001.po not found at %s", po_path)
            return

        from odoo.tools.translate import TranslationImporter
        importer = TranslationImporter(env.cr, verbose=True)
        with open(po_path, 'rb') as f:
            importer.load(f, 'po', 'ar_001', xmlids=False, module='medical_inventory')
        importer.save(overwrite=True)
        env.cr.commit()
        _logger.info("medical_inventory: Arabic translations loaded successfully")
    except Exception as e:
        _logger.warning("medical_inventory: Failed to load Arabic: %s", e)
