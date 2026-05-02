project('whatcable-linux',
  version: '0.1.0',
  meson_version: '>= 1.2.0',
)

python = import('python').find_installation('python3')
gnome = import('gnome')

pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

python.install_sources(
  files(
    'src/whatcable_linux/__init__.py',
    'src/whatcable_linux/__main__.py',
    'src/whatcable_linux/advanced_sources.py',
    'src/whatcable_linux/app.py',
    'src/whatcable_linux/cli.py',
    'src/whatcable_linux/models.py',
    'src/whatcable_linux/naming.py',
    'src/whatcable_linux/pd.py',
    'src/whatcable_linux/report.py',
    'src/whatcable_linux/summary.py',
    'src/whatcable_linux/sysfs.py',
    'src/whatcable_linux/usb_sysfs.py',
  ),
  subdir: 'whatcable_linux',
)

configure_file(
  input: 'src/whatcable-linux.in',
  output: 'whatcable-linux',
  configuration: {'PYTHON': python.full_path()},
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

install_data('data/com.nedrichards.WhatCable.desktop',
  install_dir: get_option('datadir') / 'applications',
)

install_data('data/com.nedrichards.WhatCable.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)

install_data('data/com.nedrichards.WhatCable.svg',
  install_dir: get_option('datadir') / 'icons' / 'hicolor' / 'scalable' / 'apps',
)

install_data('data/style.css', install_dir: pkgdatadir)

test(
  'unit',
  python,
  args: ['-m', 'pytest', meson.current_source_dir() / 'tests'],
  env: ['PYTHONPATH=' + meson.current_source_dir() / 'src'],
)
