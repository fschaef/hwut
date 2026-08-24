require "simplecov"
require "simplecov-cobertura"
SimpleCov.formatter = SimpleCov::Formatter::CoberturaFormatter
SimpleCov.start
require_relative "calc"
