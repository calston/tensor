require 'spec_helper'

describe 'tensor' do
  on_supported_os.each do |os, facts|
    context "on #{os}" do
      let(:facts) { facts }

      describe 'with defaults for all parameters' do
        it { is_expected.to contain_class('tensor') }
      end
    end
  end
end
