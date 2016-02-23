define tensor::output($output, $config=false) {
  file {"/etc/tensor/conf.d/output_${title}.yml":
    ensure  => present,
    content => template('tensor/tensor-output.yml.erb'),
    owner   => root,
    mode    => 0644,
    notify  => Service['tensor'],
    require => File['/etc/tensor/conf.d'],
  }
}
