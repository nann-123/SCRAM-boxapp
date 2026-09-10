
#include "CoefficientRepartition.hxx"
using namespace CoefficientRepartition;

int main(int argc, char* argv[])
{
  string config_file("config.lua");
  if (argc > 1)
    config_file = argv[1];

  string config_type("default");
  if (argc > 2)
    config_type = argv[2];

  ClassCoefficientRepartitionBase::Init(config_file);
  ClassGeneralSection::Init(config_type);

  ClassCoefficientRepartition coef(config_type);

  return 0;
}

