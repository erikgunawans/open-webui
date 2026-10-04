"""The corporate KPI 2026 catalogue behind the Ruang Pimpinan "KPI 2026" tab.

Source: the "KPI JUP 2026" sheet of `Form KPI_Individu_2026.xlsx`, as transcribed in Erik's
claude.ai/design project "KPI Dashboard 2026" (2026-10-05). Targets and definitions are company
figures, so they are served only through the RKA read grant and never ship in the frontend bundle.

The realisasi in `SAMPLE` is ILLUSTRATIVE (the design says so on screen): a starting point the
reader can overwrite, kept in their own browser. Nothing here is a reported result, and nothing a
reader types is sent back to the server.

Units: `rp` (rupiah), `pct` (a fraction, 0.88 = 88%), `count`. `cum` marks a KPI that accumulates
over the year, so its quarterly target may be taken pro-rata.
"""

from typing import Any

YEAR = 2026

PERSPECTIVES: tuple[dict[str, Any], ...] = (
    {'id': 'fin', 'name': 'Financial', 'weight': 0.30},
    {'id': 'cus', 'name': 'Customer', 'weight': 0.20},
    {'id': 'ibp', 'name': 'Internal Business Process', 'weight': 0.25},
    {'id': 'lg', 'name': 'Learning & Growth', 'weight': 0.25},
)

_HC = 'Improve Human Capital Capacity & Quality'
_OI = 'Organizational Innovation'
_HEALTH = 'Peningkatan Kesehatan Keuangan Perusahaan'
_TRUST = 'Improving Customer Trust and Satisfaction'

ITEMS: tuple[dict[str, Any], ...] = (
    {
        'id': 'k1',
        'p': 'fin',
        'so_k': 'Value Creation',
        'so_d': 'Penciptaan Keuntungan (Pendapatan) atas Produk atau Jasa yang ditawarkan',
        'name': 'Pendapatan (Unit Bisnis)',
        'definition': 'Perolehan Pendapatan Unit Bisnis Tahun 2026. Unit Bisnis I: Properti, Perparkiran. '
        'Unit Bisnis II: WTP, Konstruksi. Unit Bisnis III: SPBG, SPBE, SPBU, EBT.',
        'satuan': 'Rp',
        'unit': 'rp',
        'formula': 'Realisasi Vs Target Nilai Pendapatan Unit Bisnis 2026',
        'target': 252156802078.44,
        'weight': 0.10,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k2',
        'p': 'fin',
        'so_k': _HEALTH,
        'so_d': 'Meningkatkan profitabilitas Perusahaan',
        'name': 'Laba Bersih Positif',
        'definition': 'Mengukur keuntungan akhir perusahaan setelah semua biaya, termasuk harga pokok '
        'penjualan, biaya operasional, bunga, dan pajak, dikurangi dari total pendapatan dalam periode tertentu.',
        'satuan': 'Rp',
        'unit': 'rp',
        'formula': 'Nilai Net Income positif',
        'target': 2166258037.82,
        'weight': 0.10,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k3',
        'p': 'fin',
        'so_k': _HEALTH,
        'so_d': 'Meningkatkan profitabilitas Perusahaan',
        'name': 'Cashflow Operation Positif',
        'definition': 'Mengukur kesehatan dan efisiensi operasional inti perusahaan, menilai kemampuan '
        'menghasilkan kas untuk membayar utang dan dividen, serta memberi dasar pengambilan keputusan investasi.',
        'satuan': 'Rp',
        'unit': 'rp',
        'formula': 'Nilai Cashflow Operation positif',
        'target': 5262693597,
        'weight': 0.10,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k4',
        'p': 'cus',
        'so_k': _TRUST,
        'so_d': 'Growth Potential Customer',
        'name': 'Pertumbuhan Calon Pelanggan Potensial – Marketing',
        'definition': 'Pertumbuhan pelanggan/customer potensial unit bisnis.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target',
        'target': 0.05,
        'weight': 0.05,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k5',
        'p': 'cus',
        'so_k': _TRUST,
        'so_d': 'Peningkatan Kualitas Produk melalui Pemenuhan Standar Pelayanan Minimum Produk',
        'name': 'Tingkat Kepuasan Pelanggan',
        'definition': 'Menunjukkan tingkat kepuasan pelanggan terhadap pelayanan yang diberikan perusahaan.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target 88% pelanggan puas',
        'target': 0.88,
        'weight': 0.10,
        'monitoring': 'Tahunan',
        'cum': False,
    },
    {
        'id': 'k6',
        'p': 'cus',
        'so_k': 'Marketing & Promotion Enhancement',
        'so_d': 'Customer Engagement',
        'name': 'Jumlah Kampanye/Edukasi Energi Bersih',
        'definition': 'Pembuatan Calendar of Event satu tahun ke depan dan penyampaian Calendar of Event '
        'secara berkala kepada publik.',
        'satuan': 'Kali',
        'unit': 'count',
        'formula': 'Realisasi Vs Target',
        'target': 12,
        'weight': 0.05,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k7',
        'p': 'ibp',
        'so_k': _OI,
        'so_d': 'Monitoring Performa Bisnis Secara Berkala',
        'name': 'Pemenuhan SLA Laporan Performance',
        'definition': 'Laporan evaluasi berkala perihal monitoring performance yang dilakukan setiap bulan.',
        'satuan': 'Kali',
        'unit': 'count',
        'formula': 'Jumlah Laporan',
        'target': 12,
        'weight': 0.10,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k8',
        'p': 'ibp',
        'so_k': _OI,
        'so_d': 'Inovasi Produk untuk Menciptakan Nilai Baru bagi Barang dan Jasa yang Ditawarkan',
        'name': 'Integrasi Sistem Energi Digital',
        'definition': 'Sistem Monitoring Kinerja Unit Bisnis & Supporting (fokus bisnis yang mempertahankan '
        'pelanggan lama atau memperkuat pelanggan baru).',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target',
        'target': 1,
        'weight': 0.05,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k9',
        'p': 'ibp',
        'so_k': _OI,
        'so_d': 'Monitoring Kajian Bisnis',
        'name': 'Validation Assumption Rate',
        'definition': 'Monitoring terhadap Kajian Bisnis yang tercapai & tidak tercapai.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target',
        'target': 0.8,
        'weight': 0.05,
        'monitoring': 'Tahunan',
        'cum': False,
    },
    {
        'id': 'k10',
        'p': 'ibp',
        'so_k': _OI,
        'so_d': 'Peningkatan Business Effectiveness',
        'name': 'Progres Surveillance ISO',
        'definition': 'ISO 9001:2015 Quality Management; ISO 45001:2018 Health & Safety.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Pelaksanaan Surveillance ISO',
        'target': 1,
        'weight': 0.05,
        'monitoring': 'Tahunan',
        'cum': True,
    },
    {
        'id': 'k11',
        'p': 'lg',
        'so_k': _HC,
        'so_d': 'Optimalisasi Kinerja Organisasi',
        'name': 'Succession Rate',
        'definition': 'Mengukur sejauh mana posisi/jabatan dalam perusahaan sudah memiliki calon pengganti.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target',
        'target': 0.7,
        'weight': 0.05,
        'monitoring': 'Triwulan',
        'cum': False,
    },
    {
        'id': 'k12',
        'p': 'lg',
        'so_k': _HC,
        'so_d': 'Optimalisasi Kinerja Organisasi',
        'name': 'Competency Gap Ratio',
        'definition': 'Memastikan kesesuaian jobdesk dan level karyawan dengan membandingkan nilai suatu '
        'jabatan dengan nilai jabatan lain.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target',
        'target': 0.7,
        'weight': 0.05,
        'monitoring': 'Triwulan',
        'cum': False,
    },
    {
        'id': 'k13',
        'p': 'lg',
        'so_k': _HC,
        'so_d': 'Optimalisasi Kinerja Organisasi',
        'name': 'Employee Engagement Index',
        'definition': 'Keterlekatan karyawan terhadap organisasi.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Realisasi Vs Target',
        'target': 0.8,
        'weight': 0.05,
        'monitoring': 'Triwulan',
        'cum': False,
    },
    {
        'id': 'k14',
        'p': 'lg',
        'so_k': 'Compliance',
        'so_d': 'Pemenuhan Aspek Legalitas untuk Pelaksanaan Operasional Bisnis',
        'name': 'Nilai Implementasi GCG',
        'definition': 'Mengukur penerapan GCG JUP, terdiri dari pemutakhiran dokumen GCG: Tata Kelola '
        'Perusahaan, Board Manual, Code of Conduct.',
        'satuan': 'Jumlah',
        'unit': 'count',
        'formula': 'Nilai Assesmen',
        'target': 87,
        'weight': 0.05,
        'monitoring': 'Triwulan',
        'cum': False,
    },
    {
        'id': 'k15',
        'p': 'lg',
        'so_k': 'Compliance',
        'so_d': 'Pelaksanaan Analisis dan Pelaksanaan Mitigasi Risiko',
        'name': 'Efektivitas Manajemen Risiko Perusahaan',
        'definition': 'Efektivitas tindakan yang diambil atas identifikasi risiko & peluang.',
        'satuan': '%',
        'unit': 'pct',
        'formula': 'Pelaksanaan mitigasi / Total mitigasi',
        'target': 0.85,
        'weight': 0.05,
        'monitoring': 'Triwulan',
        'cum': False,
    },
)

# ILLUSTRATIVE year-to-date realisasi for TW I–III; TW IV empty. Not reported results.
SAMPLE: dict[str, list[float | None]] = {
    'k1': [52.4e9, 118.9e9, 181.3e9, None],
    'k2': [-0.31e9, 0.42e9, 1.12e9, None],
    'k3': [0.9e9, 2.1e9, 3.4e9, None],
    'k4': [0.012, 0.026, 0.039, None],
    'k5': [0.84, 0.85, 0.86, None],
    'k6': [3, 6, 9, None],
    'k7': [3, 6, 9, None],
    'k8': [0.20, 0.45, 0.65, None],
    'k9': [0.60, 0.68, 0.74, None],
    'k10': [0.25, 0.50, 0.90, None],
    'k11': [0.40, 0.52, 0.61, None],
    'k12': [0.55, 0.60, 0.66, None],
    'k13': [0.72, 0.74, 0.77, None],
    'k14': [80, 83, 85, None],
    'k15': [0.60, 0.70, 0.78, None],
}

SOURCE = 'Sheet "KPI JUP 2026", Form KPI_Individu_2026.xlsx'


def read_kpi() -> dict[str, Any]:
    """The catalogue as the tab reads it. Fresh containers each call, so a caller cannot mutate ours."""
    return {
        'year': YEAR,
        'source': SOURCE,
        'sample_is_illustrative': True,
        'perspectives': [dict(p) for p in PERSPECTIVES],
        'items': [dict(k) for k in ITEMS],
        'sample': {key: list(values) for key, values in SAMPLE.items()},
    }
