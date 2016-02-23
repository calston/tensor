define tensor::source($source, $interval='60.0', $config=false,
  $critical=false, $warning=false, $service_name=false, $tags=false
  ) {
  $service = $title

  file {"/etc/tensor/conf.d/${service}.yml":
    ensure  => present,
    content => template('tensor/tensor-source.yml.erb'),
    notify  => Service['tensor'],
    require => File['/etc/tensor/conf.d'],
  }
}
