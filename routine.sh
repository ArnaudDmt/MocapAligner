#!/bin/zsh

set -e



############################ Absolute paths initialization ############################

# current working directory
cwd=$(pwd)
replay_yaml="$HOME/.config/mc_rtc/controllers/Passthrough.yaml"
mc_rtc_yaml="$HOME/.config/mc_rtc/mc_rtc.yaml"
mocapPlugin_yaml="$HOME/.config/mc_rtc/plugins/MocapAligner.yaml"






if [ ! -f "$replay_yaml" ]; then
    echo "The scripts excepts to find a configuration file named $replay_yaml."
    exit
fi

createNewProject=false

# Create an array with the names of the directories
cd Projects
if [ -n "$(find . -maxdepth 1 -type d -not -path .)" ]; then
    echo "Do you want to create a new project or run an existing one?"
    select createNew in "Run existing project" "Create new project"; do
        case $createNew in
            "Run existing project" ) 
                projectNames=(*/)
                # Remove trailing slashes
                projectNames=("${projectNames[@]%/}")

                echo "Please select a project:"
                select projectName in "${projectNames[@]}"; do
                    if [[ -n $projectName ]]; then
                        break
                    else
                        echo "Invalid selection. Please try again."
                    fi
                done
                projectPath="Projects/$projectName"
                break;;
            "Create new project" ) 
                createNewProject=true
                break;;
        esac
    done
else
    createNewProject=true
fi

cd $cwd

if $createNewProject; then
    echo "Please enter the name of the name of the new project: "; 
    read projectName;

    projectPath="Projects/$projectName"
    mkdir $projectPath
    mkdir "$projectPath/raw_data"
    mkdir "$projectPath/output_data"
    
    touch "$projectPath/projectConfig.yaml"
    echo "EnabledBody: " >> "$projectPath/projectConfig.yaml"
    echo "EnabledRobot: " >> "$projectPath/projectConfig.yaml"
    if locate HartleyIEKF.so | grep install;then
        echo "Use_HartleyIEKF: " >> "$projectPath/projectConfig.yaml"
    fi
    echo "Project created. Please add the raw data of the mocap and mc_rtc's log into $projectPath/raw_data under the names mocapData.csv and logController.bin, and fill in the configuration file $projectPath/projectConfig.yaml."
    exit
fi



############################ Variables initialization ############################


# indicates if the scripts must be ran
runScript=false

# main folders
rawDataPath="$projectPath/raw_data"
outputDataPath="$projectPath/output_data"
scriptsPath="/scripts"

# files of the resulting data after each step
resampledMocapData="$outputDataPath/resampledMocapData.csv"
lightData="$outputDataPath/lightData.csv"
realignedMocapLimbData="$outputDataPath/realignedMocapLimbData.csv"
resultMocapLimbData="$outputDataPath/resultMocapLimbData.csv"

# files of the replay
logReplayCSV="$outputDataPath/logReplay.csv"
logReplayBin="$outputDataPath/logReplay.bin"

# configuration files
projectConfig="$projectPath/projectConfig.yaml"
#mocapMarkersConf="markersPlacements.yaml"



############################ Checking if a robot was given to select the mocap markers ############################


if grep -v '^#' $projectConfig | grep -q "EnabledRobot"; then
    if [[ ! $(grep 'EnabledRobot:' $projectConfig | grep -v '^#' | sed 's/EnabledRobot://' | sed 's: ::g') ]]; then
        echo "No robot was given in the configuration file $projectConfig. Use the robot defined in $mc_rtc_yaml ?"
        select useMainConfRobot in "Yes" "No"; do
            case $useMainConfRobot in
                Yes ) 
                    main_robot=$( grep 'MainRobot:' $mc_rtc_yaml | grep -v '^#' | sed 's/MainRobot: //');
                    break;;
                No ) 
                    echo "Please enter the name of the robot to add to $projectConfig: "; 
                    read main_robot;
                    break;;
            esac
        done
        sed -i "s/EnabledRobot:/& $main_robot/" $projectConfig
    fi
else
    echo "No robot was given in the configuration file $projectConfig. Use the robot defined in $mc_rtc_yaml ?"
    select useMainConfRobot in "Yes" "No"; do
        case $useMainConfRobot in
            Yes ) 
                main_robot=$( grep 'MainRobot:' $mc_rtc_yaml | grep -v '^#' | sed 's/MainRobot: //');
                break;;
            No ) 
                echo "Please enter the name of the robot to add to $projectConfig: "; 
                read main_robot;
                break;;
        esac
    done
    if [ -s $projectConfig ]; then
        awk -i inplace -v robot="$main_robot" 'FNR==1 {print "EnabledRobot:", robot}1' $projectConfig
    else
        echo "EnabledRobot: $main_robot" > $projectConfig
    fi
    
fi


############################ Checking if a mocap body was given to select the mocap markers ############################

if grep -v '^#' $projectConfig | grep -q "EnabledBody"; then
    if [[ ! $(grep 'EnabledBody:' $projectConfig | grep -v '^#' | sed 's/EnabledBody://' | sed 's: ::g') ]]; then
        echo "No mocap body was given in the configuration file $projectConfig. Please enter the name of the body to add to $projectConfig: "; 
        read body;

        sed -i "s/EnabledBody:/& $body/" $projectConfig
    fi
else
    eecho "No mocap body was given in the configuration file $projectConfig. Please enter the name of the body to add to $projectConfig: "; 
    read body;
    if [ -s $projectConfig ]; then
        awk -i inplace -v body="$body" 'FNR==1 {print "EnabledBody:", body}1' $projectConfig;
    else
        echo "EnabledBody: $body" > $projectConfig
    fi
    
fi

bodyName=$(grep 'EnabledBody:' $projectConfig | grep -v '^#' | sed 's/EnabledBody://' | sed 's: ::g');



############################ Needs the timestep to replay the log or resample the mocap's data ############################

if [ ! -f "$resampledMocapData" ] || [ ! -f "$realignedMocapLimbData" ]; then
    echo "Use the timestep defined in $mc_rtc_yaml ?"
    select useMainConfRobot in "Yes" "No"; do
        case $useMainConfRobot in
            Yes ) 
                timeStep=$( grep 'Timestep:' $mc_rtc_yaml | grep -v '^#' | sed 's/Timestep: //'); break;;
            No ) 
                echo "Please enter the timestep of the controller in milliseconds: "
                read timeStep ; break;;
        esac
    done
fi

mocapLog="$rawDataPath/mocapData.csv"
if [ -f "$mocapLog" ]; then
    echo "The log file of the mocap was found."
else
    echo "The log file of the mocap does not exist or is not named as expected. Expected: $mocapLog."
    exit
fi


############################ Handling mc_rtc's log ############################


if [ -f "$logReplayCSV" ]; then
    echo "The csv file of the replay with the observers has been found."
else
    if [ -f "$logReplayBin" ]; then
        echo "The bin file of the replay with the observers has been found. Converting to csv."
        cd $outputDataPath
        mc_bin_to_log "../$logReplayBin"
    else
        mcrtcLog="$rawDataPath/controllerLog.bin"
        if [ -f "$mcrtcLog" ]; then
            echo "The log file of the controller was found. Replaying the log with the observer."
            if grep -v '^#' $mc_rtc_yaml | grep "Plugins" | grep -v "MocapAligner"; then
                    echo "The plugin MocapAligner conflicts with another plugin in $mc_rtc_yaml. Please remove the conflicting plugin or add manually MocapAligner to the existing list."
                    exit
            fi

            if [ ! -f "$mocapPlugin_yaml" ]; then
                mkdir -p $HOME/.config/mc_rtc/plugins 
                touch $mocapPlugin_yaml
            fi
            
            if grep -v '^#' $mocapPlugin_yaml | grep -q "bodyName"; then
                sed -i "s/bodyName:.*/bodyName: $bodyName/" $mocapPlugin_yaml
            else
                if [ -s $mocapPlugin_yaml ]; then
                    awk -i inplace -v name="$bodyName" 'FNR==1 {print "bodyName:", name}1' $mocapPlugin_yaml
                else
                    echo "bodyName: $bodyName" > $mocapPlugin_yaml
                fi
            fi
            pluginWasActivated=true
            if ! grep -v '^#' $mc_rtc_yaml | grep -q "MocapAligner"; then
                pluginWasActivated=false
                echo "The plugin MocapAligner was not activated. Activating it for the replay."
                if grep -v '^#' $mc_rtc_yaml | grep "Plugins" | grep -v "MocapAligner"; then
                    echo "The replay needs to activate the plugin MocapAligner but another plugin is already enabled in $mc_rtc_yaml. Please remove the conflicting plugin or add manually MocapAligner to the existing list."
                    exit
                fi
                awk -i inplace 'FNR==1 {print "Plugins: [MocapAligner] \n"}1' $mc_rtc_yaml
            fi
            if ! grep -q "MocapVisualizer" $replay_yaml || ! grep -q "firstRun:" $replay_yaml; then
                # Execute your action here if both patterns are found
                echo "Please add the MocapVisualizer observer to the list of the observers and check that the configuration firstRun exists"
                exit
            fi
            
            sed -i "/^\([[:space:]]*firstRun: \).*/s//\1"true"/" $replay_yaml
            mc_rtc_ticker --no-sync --replay-outputs -e -l $mcrtcLog
            cd /tmp/
            LOG=$(find -iname "mc-control*" | grep "Passthrough" | grep -v "latest" | grep ".bin" | sort | tail -1)
            echo "Copying the replay's bin file ($LOG) to the output_data folder as logReplay.bin"
            mv $LOG $cwd/$logReplayBin
            cd $cwd/$outputDataPath
            mc_bin_to_log logReplay.bin
            cd $cwd

            if ! $pluginWasActivated; then
                sed -i '1d' $mc_rtc_yaml
            fi

        else
            echo "The log file of the controller does not exist or is not named as expected. Expected: $mcrtcLog."
            exit
        fi
    fi
fi


############################ Handling mocap's data ############################

cd $cwd

if [ -f "$resampledMocapData" ]; then
    echo "The mocap's data has already been resampled. Using the existing data."
else
    echo "Starting the resampling of the mocap's signal."
    cd $cwd/$scriptsPath
    python resampleAndExtract_fromMocap.py "$timeStep" "False" "y" "../$projectPath"
    echo "Resampling of the mocap's signal completed."
    runScript=true
fi

cd $cwd

if [ -f "$lightData" ]; then
    echo "The light version of the observer's data has already been extracted. Using the existing data."
else
    echo "Starting the extraction of the light version of the observer's data."
    cd $cwd/$scriptsPath
    python extractLightReplayVersion.py "../$projectPath"
    echo "Extraction of the light version of the observer's data completed."
    runScript=true
fi
echo 

cd $cwd


if [ -f "$realignedMocapLimbData" ] && ! $runScript; then
    echo "The temporally aligned version of the mocap's data already exists. Using the existing data."
else
    echo "Starting the cross correlation for temporal data alignement."
    cd $cwd/$scriptsPath
    python crossCorrelation.py "$timeStep" "False" "y" "../$projectPath"
    echo "Temporal alignement of the mocap's data with the observer's data completed."
    runScript=true
fi
echo 

cd $cwd


if [ -f "$resultMocapLimbData" ] && ! $runScript; then
    echo "The mocap's data has already been completely treated."
    echo "Do you want to match the pose of the mocap and of the observer at a different timing?"
    select changeMatchTime in "No" "Yes"; do
        case $changeMatchTime in
            No ) break;;
            Yes ) echo "Please enter the time at which you want the pose of the mocap and the one of the observer must match: " ; read matchTime; cd $cwd/$scriptsPath; python matchInitPose.py "$matchTime" "False" "y" "../$projectPath"; echo "Matching of the pose of the mocap with the pose of the observer completed."; break;;
        esac
    done
else
    # Prompt the user for input
    echo "Please enter the time at which you want the pose of the mocap and the one of the observer must match: "
    read matchTime
    cd $cwd/$scriptsPath
    python matchInitPose.py "$matchTime" "False" "y" "../$projectPath"
    echo "Matching of the pose of the mocap with the pose of the observer completed."
fi

cd $cwd


############################ Replaying the final result ############################

echo "Do you want to replay the log with the obtained mocap's data?"
select replayWithMocap in "Yes" "No"; do
    case $replayWithMocap in
        Yes ) mcrtcLog="$rawDataPath/controllerLog.bin"; pwd; echo $mcrtcLog ; sed -i "/^\([[:space:]]*firstRun: \).*/s//\1"false"/" $replay_yaml; sed -i "/^\([[:space:]]*mocapBodyName: \).*/s//\1"$bodyName"/" $replay_yaml; mc_rtc_ticker --no-sync --replay-outputs -e -l $mcrtcLog; break;;
        No ) exit;;
    esac
done

echo "The pipeline finished without any issue. If you are not satisfied with the result, please re-run the scripts one by one and help yourself with the logs for the debug. Please also make sure that the time you set for the matching of the mocap and the observer is correct."