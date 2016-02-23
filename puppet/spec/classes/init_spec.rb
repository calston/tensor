require 'spec_helper'
describe 'tensor' do

  context 'with defaults for all parameters' do
    it { should contain_class('tensor') }
  end
end
