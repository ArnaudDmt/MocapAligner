#include "MocapAligner.h"

#include <mc_control/GlobalPluginMacros.h>
#include <mc_state_observation/conversions/kinematics.h>

namespace mc_plugin
{

MocapAligner::~MocapAligner() = default;

void MocapAligner::init(mc_control::MCGlobalController & controller, const mc_rtc::Configuration & config)
{
  robot_ = config("robot", controller.controller().robot().name());
  mocapBodyName_ = static_cast<std::string>(config("bodyName"));

  if(!controller.controller().realRobot(robot_).hasBody(mocapBodyName_))
  {
    mc_rtc::log::error("The body given in the configuration of the MocapAligner plugin does not exist in {}. Here is "
                       "the list of all the bodies.",
                       robot_);
    for(auto & test : controller.controller().realRobot(robot_).mb().bodies())
    {
      std::cout << std::endl << test.name() << std::endl;
    }
    mc_rtc::log::error_and_throw("Please give an available body.");
  }

  auto & logger = (const_cast<mc_control::MCController &>(controller.controller())).logger();
  mc_state_observation::conversions::kinematics::addToLogger(logger, worldMocapBodyKine_, "MocapAligner_worldBodyKine");
}

void MocapAligner::reset(mc_control::MCGlobalController & controller) {}

void MocapAligner::before(mc_control::MCGlobalController &) {}

void MocapAligner::after(mc_control::MCGlobalController & controller)
{
  worldMocapBodyKine_ = mc_state_observation::conversions::kinematics::fromSva(
      controller.controller().realRobot(robot_).bodyPosW(mocapBodyName_),
      stateObservation::kine::Kinematics::Flags::pose);
}

mc_control::GlobalPlugin::GlobalPluginConfiguration MocapAligner::configuration()
{
  mc_control::GlobalPlugin::GlobalPluginConfiguration out;
  out.should_run_before = true;
  out.should_run_after = true;
  out.should_always_run = true;
  return out;
}

} // namespace mc_plugin

EXPORT_MC_RTC_PLUGIN("MocapAligner", mc_plugin::MocapAligner)
