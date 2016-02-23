# TODO: Document
define tensor::puppetping($service='ping', $route=false, $query='kernel="Linux"') {
  $orghosts = query_nodes($query)

  file { '/etc/tensor/conf.d/puppet_pings.yml':
    ensure  => present,
    content => template('tensor/puppet_pings.yml.erb'),
    owner   => root,
    mode    => '0644',
    notify  => Service['tensor'],
    require => File['/etc/tensor/conf.d'],
  }
}
