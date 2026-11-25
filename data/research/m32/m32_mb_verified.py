"""M32 Task 1 verified ASUS motherboard evidence (data module).

One row per verified SKU: MPN (ASUS eShop/distributor P/N, human-citation),
per-SKU spec URL (official techspec/model-spec page), page-transcribed spec,
and notes (diffs vs M3.1 claimed_spec_json + MPN provenance). Page text is
authoritative over claimed_spec_json. ``pcie_slots`` stores the COUNT of
physical expansion slots listed on the page (x16 + x16(x4) + x16(x2) + x1).
"""

M32_ACCESS = "2026-11-23"
M32_APPROVER = "m32-curator"

VERIFIED_MB = {
    "238": {
        "mpn": "90MB1BS0-M0AAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-b650-plus/techspec/"),
        "spec": {"socket": "AM5", "chipset": "B650",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 2, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "2 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 4.0 x16 (CPU) + 1 x PCIe 4.0 x16 (x4) + "
                     "1 x PCIe 4.0 x16 (x2) + 1 x PCIe 4.0 x1"),
        "mpn_url": ("https://eshop.asus.com/ca-en/"
                    "90mb1bs0-m0aay0-prime-b650-plus.html"),
        "note": ("claimed m2_slots=3 -> page 2; claimed pcie_slots=5 -> "
                 "page 4 physical slots; MPN per ASUS eShop Canada P/N row"),
    },
    "239": {
        "mpn": "90MB1BZ0-M0AAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "tuf-gaming/tuf-gaming-b650-plus-wifi/techspec/"),
        "spec": {"socket": "AM5", "chipset": "B650",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 3, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "3 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 4.0 x16 + 1 x PCIe 4.0 x16 (x4) + "
                     "1 x PCIe 4.0 x16 (x2) + 1 x PCIe 4.0 x1"),
        "mpn_url": ("https://eshop.asus.com/us/"
                    "90mb1bz0-m0aay0-tuf-gaming-b650-plus-wifi.html"),
        "note": ("claimed m2_slots=4 -> page 3; MPN per ASUS eShop USA "
                 "P/N row"),
    },
    "240": {
        "mpn": "90MB1BQ0-M0AAY0",
        "url": ("https://rog.asus.com/motherboards/rog-strix/"
                "rog-strix-b650e-f-gaming-wifi-model/spec"),
        "spec": {"socket": "AM5", "chipset": "B650E",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 3, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "3 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": "1 x PCIe 5.0 x16 + 3 x PCIe 4.0 x1",
        "mpn_url": ("https://shop.asus.com/us/"
                    "90mb1bq0-m0aay0-rog-strix-b650e-f-gaming-wifi.html"),
        "note": ("claimed pcie_slots=5 -> page 4; MPN per ASUS eShop USA "
                 "product page P/N"),
    },
    "248": {
        "mpn": "90MB1CK0-M1EAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-z790-p/techspec/"),
        "spec": {"socket": "LGA1700", "chipset": "Z790",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 3, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "3 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": "1 x PCIe 5.0 x16 + 1 x PCIe 4.0 x16 + 2 x PCIe 4.0 x1",
        "mpn_url": "https://webshop.asus.com/ch-en/90MB1CK0-M1EAY0/PRIME-Z790-P",
        "note": ("claimed m2_slots=4 -> page 3; claimed pcie_slots=5 -> "
                 "page 4; MPN per ASUS webshop CH product number row"),
    },
    "253": {
        "mpn": "90MB1EF0-M1AAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-b760-plus/techspec/"),
        "spec": {"socket": "LGA1700", "chipset": "B760",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 3, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "3 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 5.0 x16 + 1 x PCIe 4.0 x16 (x4) + "
                     "2 x PCIe 4.0 x1"),
        "mpn_url": ("https://eshop.asus.com/ca-en/"
                    "90mb1ef0-m1aay0-prime-b760-plus.html"),
        "note": ("claimed pcie_slots=5 -> page 4; MPN per ASUS eShop "
                 "Canada P/N row"),
    },
    "259": {
        "mpn": "90MB1EG0-M0EAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-b650m-a-wifi-ii/techspec/"),
        "spec": {"socket": "AM5", "chipset": "B650",
                 "form_factor": "mATX", "ram_type": "DDR5",
                 "ram_slots": 4, "max_ram_gb": 192, "m2_slots": 2,
                 "sata_ports": 4, "pcie_slots": 3},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "2 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": "1 x PCIe 4.0 x16 + 2 x PCIe 4.0 x1",
        "mpn_url": "https://www.lasystems.be/en/asus-90mb1eg0-m0eay0",
        "note": ("no material diff vs claim; MPN per LASystems distributor "
                 "product code (90MB1EG0-M0EAY0)"),
    },
    "261": {
        "mpn": "90MB1BU0-M0EAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-x670-p/techspec/"),
        "spec": {"socket": "AM5", "chipset": "X670", "form_factor": "ATX",
                 "ram_type": "DDR5", "ram_slots": 4, "max_ram_gb": 256,
                 "m2_slots": 3, "sata_ports": 6, "pcie_slots": 5},
        "mem_row": "4 x DIMM, Max. 256GB, DDR5",
        "sto_row": "3 x M.2 slots, 6 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 5.0 x16 + 1 x PCIe 4.0 x16 (x4) + "
                     "3 x PCIe 4.0 x1"),
        "mpn_url": "https://www.senetic.no/product/90MB1BU0-M0EAY0",
        "note": ("claimed max_ram_gb=192 -> page 256; claimed m2_slots=4 -> "
                 "page 3; claimed sata_ports=4 -> page 6; claimed "
                 "pcie_slots=5 matches page; MPN per Senetic distributor "
                 "part number row (non-WIFI variant 90MB1BU0-M0EAY0)"),
    },
    "266": {
        "mpn": "90MB1D80-MVAAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "tuf-gaming/tuf-gaming-z790-plus-wifi/techspec/"),
        "spec": {"socket": "LGA1700", "chipset": "Z790",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 4, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "4 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 5.0 x16 + 1 x PCIe 4.0 x16 + "
                     "2 x PCIe 4.0 x1"),
        "mpn_url": ("https://eshop.asus.com/ca-en/"
                    "90mb1d80-mvaay0-tuf-gaming-z790-plus-wifi.html"),
        "note": ("no material diff vs claim; MPN per ASUS eShop Canada "
                 "P/N row"),
    },
    "270": {
        "mpn": "90MB1BF0-M0EAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "tuf-gaming/tuf-gaming-b650m-plus-wifi/techspec/"),
        "spec": {"socket": "AM5", "chipset": "B650",
                 "form_factor": "mATX", "ram_type": "DDR5",
                 "ram_slots": 4, "max_ram_gb": 256, "m2_slots": 2,
                 "sata_ports": 4, "pcie_slots": 3},
        "mem_row": "4 x DIMM, Max. 256GB, DDR5",
        "sto_row": "2 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 4.0 x16 + 1 x PCIe 4.0 x16 (x4) + "
                     "1 x PCIe 4.0 x1"),
        "mpn_url": ("https://eshop.asus.com/ca-en/"
                    "90mb1bf0-m0aay0-tuf-gaming-b650m-plus-wifi.html"),
        "note": ("claimed max_ram_gb=192 -> page 256; MPN per ASUS eShop "
                 "Canada P/N row"),
    },
    "274": {
        "mpn": "90MB1EK0-M1EAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-b760m-a/techspec/"),
        "spec": {"socket": "LGA1700", "chipset": "B760",
                 "form_factor": "mATX", "ram_type": "DDR5",
                 "ram_slots": 4, "max_ram_gb": 256, "m2_slots": 2,
                 "sata_ports": 4, "pcie_slots": 3},
        "mem_row": "4 x DIMM, Max. 256GB, DDR5",
        "sto_row": "2 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": "1 x PCIe 4.0 x16 + 2 x PCIe 4.0 x1",
        "mpn_url": ("https://shop.asus.com/us/"
                    "90mb1ei0-mvaay0-prime-b760m-a-ax.html"),
        "note": ("claimed max_ram_gb=192 -> page 256; page form factor "
                 "mATX matches claim; MPN: PRIME B760M-A family P/N "
                 "90MB1EK0-M1EAY0 per ASUS eShop USA family listing "
                 "(B760M-A AX page shows sibling P/N 90MB1EI0-MVAAY0)"),
    },
    "278": {
        "mpn": "90MB1ER0-MVAAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "tuf-gaming/tuf-gaming-b760-plus-wifi/techspec/"),
        "spec": {"socket": "LGA1700", "chipset": "B760",
                 "form_factor": "ATX", "ram_type": "DDR5", "ram_slots": 4,
                 "max_ram_gb": 192, "m2_slots": 3, "sata_ports": 4,
                 "pcie_slots": 4},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "3 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": ("1 x PCIe 5.0 x16 + 1 x PCIe 4.0 x16 (x4) + "
                     "1 x PCIe 4.0 x16 (x2) + 1 x PCIe 4.0 x1"),
        "mpn_url": "https://www.lasystems.be/en/asus-90mb1er0-m0eay0",
        "note": ("claimed pcie_slots=5 -> page 4; MPN per LASystems "
                 "distributor product code (90MB1ER0-M0EAY0 retail suffix; "
                 "MVAAY0 per ASUS eShop family listing)"),
    },
    "283": {
        "mpn": "90MB1F40-M0EAY0",
        "url": ("https://www.asus.com/za/motherboards-components/"
                "motherboards/prime/prime-a620m-k/techspec/"),
        "spec": {"socket": "AM5", "chipset": "A620",
                 "form_factor": "mATX", "ram_type": "DDR5",
                 "ram_slots": 2, "max_ram_gb": 96, "m2_slots": 1,
                 "sata_ports": 4, "pcie_slots": 2},
        "mem_row": "2 x DIMM, Max. 96GB, DDR5",
        "sto_row": "1 x M.2 slot, 4 x SATA 6Gb/s ports",
        "pcie_row": "1 x PCIe 4.0 x16 + 1 x PCIe 4.0 x1",
        "mpn_url": "https://www.eo.cz/ZA20070177947-asus-prime-a620mk-am5-matx.html",
        "note": ("claimed sata_ports=2 -> page 4; MPN per EO.CZ distributor "
                 "product code row (90MB1F40-M0EAY0)"),
    },
    "289": {
        "mpn": "90MB1EH0-M0EAY0",
        "url": ("https://www.asus.com/motherboards-components/motherboards/"
                "prime/prime-b650m-a-ii/techspec/"),
        "spec": {"socket": "AM5", "chipset": "B650",
                 "form_factor": "mATX", "ram_type": "DDR5",
                 "ram_slots": 4, "max_ram_gb": 192, "m2_slots": 2,
                 "sata_ports": 4, "pcie_slots": 3},
        "mem_row": "4 x DIMM, Max. 192GB, DDR5",
        "sto_row": "2 x M.2 slots, 4 x SATA 6Gb/s ports",
        "pcie_row": "1 x PCIe 4.0 x16 + 2 x PCIe 4.0 x1",
        "mpn_url": "https://welltechgroup.co.th/product/asus-prime-b650m-a-ii-90mb1eh0",
        "note": ("no material diff vs claim; MPN base 90MB1EH0 per "
                 "distributor listing; retail suffix -M0EAY0 (eShop also "
                 "shows CSM variant -M0AAYC); claimed max_ram_gb=192 "
                 "matches page"),
    },
}
