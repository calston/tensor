# TODO: Document
class tensor(
    $interval=1.0,
    $default_ttl=60.0,
    $outputs={},
    $sources={}
  ) {

  apt::source {'tensor':
    location   => 'https://calston.github.io/tensor/ubuntu',
    repos      => 'main',
    key        => '2B2A5480',
    key_server => 'keyserver.ubuntu.com'
  }

  package{'tensor':
    ensure  => latest,
    require => Apt::Source['tensor']
  }

  service{'tensor':
    ensure  => running,
    require => Package['tensor']
  }

  file{'/etc/tensor/conf.d':
    ensure  => directory,
    require => Package['tensor']
  }

  file{'/etc/tensor/tensor.yml':
    ensure  => present,
    content => template('tensor/tensor.yml.erb'),
    notify  => Service['tensor'],
    require => File['/etc/tensor/conf.d'],
  }

  create_resources(tensor::output, $outputs)

  create_resources(tensor::source, $sources)
}

