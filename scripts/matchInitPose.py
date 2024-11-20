import sys
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
import plotly.graph_objects as go
import numba

import yaml


###############################  Main variables initialization  ###############################

path_to_project = ".."

averageInterval = 10
displayLogs = True
matchTime = 0
scriptName = "matchInitPose"


###############################  User inputs  ###############################


if(len(sys.argv) > 1):
    matchTime = int(sys.argv[1])
    if(len(sys.argv) > 2):
        displayLogs = sys.argv[2].lower() == 'true'
    if(len(sys.argv) > 4):
        path_to_project = sys.argv[4]
else:
    matchTime = float(input("When do you want the mocap pose to match the observer's one? "))


# Load the CSV files into pandas dataframes
df_Observers = pd.read_csv(f'{path_to_project}/output_data/lightData.csv', delimiter=';')
mocapData = pd.read_csv(f'{path_to_project}/output_data/synchronizedMocapLimbData.csv', delimiter=';')



###############################  Function definitions  ###############################


@numba.njit
def continuous_euler(angles: np.ndarray):
    continuous_angles = np.empty_like(angles)
    continuous_angles[0] = angles[0]
    for i in range(1, len(angles)):
        diff = angles[i] - angles[i-1]
        # Check each element of the diff array
        for j in range(len(diff)):
            if diff[j] > np.pi:
                diff[j] -= 2*np.pi
            elif diff[j] < -np.pi:
                diff[j] += 2*np.pi
        continuous_angles[i] = continuous_angles[i-1] + diff
    return continuous_angles

@numba.njit
def normalize(v: np.ndarray):
        norm = np.linalg.norm(v)
        if norm == 0: 
            return v
        return v / norm

def get_invariant_orthogonal_vector(Rhat: np.ndarray, Rtez: np.ndarray):
            epsilon = 2.2204460492503131e-16
            Rhat_Rtez = np.dot(Rhat, Rtez)
            if np.all(np.abs(Rhat_Rtez[:2]) < epsilon):
                return np.array([1, 0, 0])
            else:
                return np.array([Rhat_Rtez[1], -Rhat_Rtez[0], 0])

def merge_tilt_with_yaw_axis_agnostic(Rtez: np.ndarray, R2: np.ndarray):
        ez = np.array([0, 0, 1])
        v1 = Rtez
    
        m = get_invariant_orthogonal_vector(R2, Rtez)
        m = m / np.linalg.norm(m)

        ml = np.dot(R2.T, m)

        R_temp1 = np.column_stack((np.cross(m, ez), m, ez))

        R_temp2 = np.vstack((np.cross(ml, v1).T, ml.T, v1.T))

        return np.dot(R_temp1, R_temp2)

###############################  Poses retrieval  ###############################

# Extracting the poses related to the mocap

world_MocapLimb_Pos = np.array([mocapData['worldMocapLimbPos_x'], mocapData['worldMocapLimbPos_y'], mocapData['worldMocapLimbPos_z']]).T
world_MocapLimb_Ori_R = R.from_quat(mocapData[["worldMocapLimbOri_qx", "worldMocapLimbOri_qy", "worldMocapLimbOri_qz", "worldMocapLimbOri_qw"]].values)

# Extracting the poses coming from mc_rtc
world_RefObserverLimb_Pos = np.array([df_Observers['MocapAligner_worldBodyKine_position_x'], df_Observers['MocapAligner_worldBodyKine_position_y'], df_Observers['MocapAligner_worldBodyKine_position_z']]).T
world_RefObserverLimb_Ori_R = R.from_quat(df_Observers[["MocapAligner_worldBodyKine_ori_x", "MocapAligner_worldBodyKine_ori_y", "MocapAligner_worldBodyKine_ori_z", "MocapAligner_worldBodyKine_ori_w"]].values)
# We get the inverse of the orientation as the inverse quaternion was stored
world_RefObserverLimb_Ori_R = world_RefObserverLimb_Ori_R.inv()


overlapIndex = mocapData['overlapTime']


#####################  Orientation and position difference wrt the initial frame  #####################

initPosesAndTransfos = {}

def compute_orientation_position_difference(
        world_ObserverLimb_Pos: np.ndarray, 
        world_ObserverLimb_Ori_R
    ) -> None:
    """
    Computes the position and orientation differences with respect to the initial frame
    and writes the results to the provided dictionary.
    
    Parameters:
        dictToWrite (dict): Dictionary to store computed transformations.
        dataName (str): Key under which data will be stored in dictToWrite.
        world_ObserverLimb_Pos (np.ndarray): Array of position vectors over time.
        world_ObserverLimb_Ori_R (Rotation): Array of orientation Rotation objects over time.
        
    Note:
        Updates dictToWrite with transformed positions and continuous orientation in Euler angles.
    """

    if not world_ObserverLimb_Pos.size or not len(world_ObserverLimb_Ori_R):
        raise ValueError("Input position or orientation arrays are empty.")

    # Euler angles for the entire orientation series
    ori_euler = world_ObserverLimb_Ori_R.as_euler("xyz")
    ori_euler_continuous = continuous_euler(ori_euler)
    
    # Initial orientation and position
    initial_ori = world_ObserverLimb_Ori_R[0]
    initial_pos = world_ObserverLimb_Pos[0]
    
    # Position difference transformation
    pos_transfo = initial_ori.apply(world_ObserverLimb_Pos - initial_pos, inverse=True)

    # Orientation difference transformation
    ori_transfo = initial_ori.inv() * world_ObserverLimb_Ori_R
    ori_transfo_euler = ori_transfo.as_euler("xyz")
    ori_transfo_euler_continuous = continuous_euler(ori_transfo_euler)
    
    # Store results in dictToWrite
    return {
        "pos_transfo": pos_transfo,
        "ori_transfo_euler_continuous": ori_transfo_euler_continuous,
        "ori_euler_continuous": ori_euler_continuous
    }


initPosesAndTransfos["Mocap"] = compute_orientation_position_difference(world_MocapLimb_Pos, world_MocapLimb_Ori_R)
initPosesAndTransfos["RefObserver"] = compute_orientation_position_difference(world_RefObserverLimb_Pos, world_RefObserverLimb_Ori_R)


if(displayLogs):
    figInitPose = go.Figure()

    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["ori_euler_continuous"][:,0], mode='lines', name='world_MocapLimb_Ori_roll'))
    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["ori_euler_continuous"][:,1], mode='lines', name='world_MocapLimb_Ori_pitch'))
    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["ori_euler_continuous"][:,2], mode='lines', name='world_MocapLimb_Ori_yaw'))

    figInitPose.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_euler_continuous"][:,0], mode='lines', name='world_RefObserverLimb_Ori_roll'))
    figInitPose.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_euler_continuous"][:,1], mode='lines', name='world_RefObserverLimb_Ori_pitch'))
    figInitPose.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_euler_continuous"][:,2], mode='lines', name='world_RefObserverLimb_Ori_yaw'))


    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=world_MocapLimb_Pos[:,0], mode='lines', name='world_MocapLimb_Pos_x'))
    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=world_MocapLimb_Pos[:,1], mode='lines', name='world_MocapLimb_Pos_y'))
    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=world_MocapLimb_Pos[:,2], mode='lines', name='world_MocapLimb_Pos_z'))

    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=world_RefObserverLimb_Pos[:,0], mode='lines', name='world_RefObserverLimb_Pos_x'))
    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=world_RefObserverLimb_Pos[:,1], mode='lines', name='world_RefObserverLimb_Pos_y'))
    figInitPose.add_trace(go.Scatter(x=mocapData["t"], y=world_RefObserverLimb_Pos[:,2], mode='lines', name='world_RefObserverLimb_Pos_z'))

    figInitPose.update_layout(title=f"{scriptName}: Poses before matching")


    # Show the plotly figure
    figInitPose.show()


    figTransfoInit = go.Figure()

    figTransfoInit.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["ori_transfo_euler_continuous"][:,0], mode='lines', name='world_MocapLimb_Ori_transfo_roll'))
    figTransfoInit.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["ori_transfo_euler_continuous"][:,1], mode='lines', name='world_MocapLimb_Ori_transfo_pitch'))
    figTransfoInit.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["ori_transfo_euler_continuous"][:,2], mode='lines', name='world_MocapLimb_Ori_transfo_yaw'))

    figTransfoInit.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_transfo_euler_continuous"][:,0], mode='lines', name='world_RefObserverLimb_Ori_transfo_roll'))
    figTransfoInit.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_transfo_euler_continuous"][:,1], mode='lines', name='world_RefObserverLimb_Ori_transfo_pitch'))
    figTransfoInit.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_transfo_euler_continuous"][:,2], mode='lines', name='world_RefObserverLimb_Ori_transfo_yaw'))


    figTransfoInit.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["pos_transfo"][:,0], mode='lines', name='world_MocapLimb_pos_transfo_x'))
    figTransfoInit.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["pos_transfo"][:,1], mode='lines', name='world_MocapLimb_pos_transfo_y'))
    figTransfoInit.add_trace(go.Scatter(x=mocapData["t"], y=initPosesAndTransfos["Mocap"]["pos_transfo"][:,2], mode='lines', name='world_MocapLimb_pos_transfo_z'))

    figTransfoInit.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["pos_transfo"][:,0], mode='lines', name='world_RefObserverLimb_pos_transfo_x'))
    figTransfoInit.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["pos_transfo"][:,1], mode='lines', name='world_RefObserverLimb_pos_transfo_y'))
    figTransfoInit.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["pos_transfo"][:,2], mode='lines', name='world_RefObserverLimb_pos_transfo_z'))

    figTransfoInit.update_layout(title=f"{scriptName}: Transformations before matching")


    # Show the plotly figures
    figTransfoInit.show()


###############################  Average around matching point  ###############################


# Find the index in the pandas dataframe that corresponds to the input time
matchIndex = mocapData[mocapData['t'] == matchTime].index[0]


def get_mocap_pitch_offset_from_accelero():
    ya = np.array(df_Observers[['Accelerometer_linearAcceleration_x', 'Accelerometer_linearAcceleration_y', 'Accelerometer_linearAcceleration_z']])

    avg_interval = 10
    Rt_ez_accelero = ya / np.linalg.norm(ya, axis = 1, keepdims=True)
    Rt_ez_accelero_avg = np.mean(Rt_ez_accelero[:avg_interval], axis=0)
    init_mocap_avg_R_quat = np.mean(world_MocapLimb_Ori_R.as_quat()[:avg_interval], axis=0)

    print(Rt_ez_accelero_avg.shape)
    print(init_mocap_avg_R_quat.shape)
    true_R_init_avg_quat = R.from_matrix(merge_tilt_with_yaw_axis_agnostic(Rt_ez_accelero_avg, R.from_quat(init_mocap_avg_R_quat).as_matrix()))
    mocap_pitch_offset = R.from_quat(init_mocap_avg_R_quat).inv() * true_R_init_avg_quat
    print(f"The offset on the mocap pitch is not contained in the configuration file, computing it from the accelerometer signal: {mocap_pitch_offset.as_quat()}")

    return mocap_pitch_offset

def get_mocap_pitch_offset_from_yaml(robot_name):
    # Iterate over the robots
    for robot in markers_yamlData['robots']:
        # If the robot name matches
        if robot['name'] == robot_name:
            try:
                mocap_pitch_offset = R.from_quat(robot['mocap_pitch_offset'])
                print("Retrieved the offset on the mocap pitch from the configuration file.")
                return mocap_pitch_offset
            except:
                return get_mocap_pitch_offset_from_accelero()
            

    return get_mocap_pitch_offset_from_accelero()
            


with open('../markersPlacements.yaml', 'r') as file:
    try:
        markers_yaml_str = file.read()
        markers_yamlData = yaml.safe_load(markers_yaml_str)
    except yaml.YAMLError as exc:
        print(exc)

with open(f'{path_to_project}/projectConfig.yaml', 'r') as file:
    try:
        projConf_yaml_str = file.read()
        projConf_yamlData = yaml.safe_load(projConf_yaml_str)
    except yaml.YAMLError as exc:
        print(exc)

# Get the value of EnabledRobot and EnabledBody
enabled_robot = projConf_yamlData.get('EnabledRobot')

# Check if EnabledRobot exists and is uncommented
if enabled_robot is None:
    print("EnabledRobot does not exist or is commented out.")
    enabled_robot = input("Please enter the name of the robot: ")


# Get the markers and print them
mocap_pitch_offset = get_mocap_pitch_offset_from_yaml(enabled_robot)


def compute_aligned_pose(
        world_ObserverLimb_Pos: np.ndarray, 
        world_ObserverLimb_Ori_R,
        matchIndex: int, 
        averageInterval: int
    ):
    """
    Aligns the position and orientation of the Observer limb with respect to the reference Observer limb
    at a specific match index, allowing the yaw of the Observer limb to match the reference at the given time.
    
    Parameters:
        world_ObserverLimb_Pos (np.ndarray): Array of Observer limb positions over time.
        world_ObserverLimb_Ori_R (Rotation): Rotation array of Observer limb orientations over time.
        world_RefObserverLimb_Pos (np.ndarray): Array of reference Observer limb positions over time.
        world_RefObserverLimb_Ori_R (Rotation): Rotation array of reference Observer limb orientations over time.
        matchIndex (int): The index at which the alignment is performed.
        averageInterval (int): Interval size around matchIndex for averaging.
        
    Returns:
        dict: Dictionary containing new aligned position and orientation for the Observer limb.
    """
    
    # Define lower index for averaging, clamping to zero if negative
    lowerIndex = max(matchIndex - averageInterval, 0)
    
    # Zero out overlap index entries up to matchIndex
    overlapIndex = np.zeros_like(world_ObserverLimb_Pos, dtype=int)
    overlapIndex[:matchIndex] = 0

    # Average positions around matchIndex
    world_ObserverLimb_Pos_avg = np.mean(world_ObserverLimb_Pos[lowerIndex:matchIndex + averageInterval], axis=0)
    world_RefObserverLimb_Pos_avg = np.mean(world_RefObserverLimb_Pos[lowerIndex:matchIndex + averageInterval], axis=0)

    # Convert orientations to quaternions and average
    world_ObserverLimb_Ori_Quat = world_ObserverLimb_Ori_R.as_quat()
    world_RefObserverLimb_Ori_Quat = world_RefObserverLimb_Ori_R.as_quat()

    world_ObserverLimb_Ori_Quat_avg = np.mean(world_ObserverLimb_Ori_Quat[lowerIndex:matchIndex + averageInterval], axis=0)
    world_RefObserverLimb_Ori_Quat_avg = np.mean(world_RefObserverLimb_Ori_Quat[lowerIndex:matchIndex + averageInterval], axis=0)

    # Convert averaged quaternions to rotation matrices
    world_ObserverLimb_Ori_R_avg = R.from_quat(normalize(world_ObserverLimb_Ori_Quat_avg))
    world_RefObserverLimb_Ori_R_avg = R.from_quat(normalize(world_RefObserverLimb_Ori_Quat_avg))

    # Compute the transformation to align Observer limb orientation with reference
    world_ObserverLimb_Ori_R_transfo = world_ObserverLimb_Ori_R_avg.inv() * world_ObserverLimb_Ori_R
 
 
    # Adjust yaw to match with reference Observer at match time
    mergedOriAtMatch = merge_tilt_with_yaw_axis_agnostic(
        world_ObserverLimb_Ori_R_avg.apply(np.array([0, 0, 1]), inverse=True),
        world_RefObserverLimb_Ori_R_avg.as_matrix()
    )
    mergedOriAtMatch_R = R.from_matrix(mergedOriAtMatch)
    new_world_ObserverLimb_Ori_R = mergedOriAtMatch_R * world_ObserverLimb_Ori_R_transfo

    # Align position
    new_world_ObserverLimb_Pos = world_RefObserverLimb_Pos_avg + \
        (mergedOriAtMatch_R * world_ObserverLimb_Ori_R_avg.inv()).apply(
            world_ObserverLimb_Pos - world_ObserverLimb_Pos_avg
        )

    return {
        "aligned_position": new_world_ObserverLimb_Pos,
        "aligned_orientation": new_world_ObserverLimb_Ori_R
    }

alignedPoses = {}
alignedPoses["Mocap"] =  compute_aligned_pose(
        world_MocapLimb_Pos, 
        world_MocapLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

# Once the initial pose of the mocap has been matched with the one of the observer, we correct the pitch of the mocap as there might be an offset due to the marker placements
alignedPoses["Mocap"]["aligned_orientation"] = alignedPoses["Mocap"]["aligned_orientation"] * mocap_pitch_offset
new_world_MocapLimb_Ori_quat = alignedPoses["Mocap"]["aligned_orientation"].as_quat()

mocapData['worldMocapLimbPos_x'] = alignedPoses["Mocap"]["aligned_position"][:,0]
mocapData['worldMocapLimbPos_y'] = alignedPoses["Mocap"]["aligned_position"][:,1]
mocapData['worldMocapLimbPos_z'] = alignedPoses["Mocap"]["aligned_position"][:,2]
mocapData['worldMocapLimbOri_qx'] = new_world_MocapLimb_Ori_quat[:,0]
mocapData['worldMocapLimbOri_qy'] = new_world_MocapLimb_Ori_quat[:,1]
mocapData['worldMocapLimbOri_qz'] = new_world_MocapLimb_Ori_quat[:,2]
mocapData['worldMocapLimbOri_qw'] = new_world_MocapLimb_Ori_quat[:,3]

df_Observers['Mocap_pos_x'] = alignedPoses["Mocap"]["aligned_position"][:,0]
df_Observers['Mocap_pos_y'] = alignedPoses["Mocap"]["aligned_position"][:,1]
df_Observers['Mocap_pos_z'] = alignedPoses["Mocap"]["aligned_position"][:,2]
df_Observers['Mocap_ori_x'] = new_world_MocapLimb_Ori_quat[:,0]
df_Observers['Mocap_ori_y'] = new_world_MocapLimb_Ori_quat[:,1]
df_Observers['Mocap_ori_z'] = new_world_MocapLimb_Ori_quat[:,2]
df_Observers['Mocap_ori_w'] = new_world_MocapLimb_Ori_quat[:,3]
df_Observers['Mocap_datasOverlapping'] = mocapData['overlapTime'].apply(lambda x: 'Datas overlap' if x == 1 else 'Datas not overlapping')


if 'KO_posW_tx' in df_Observers.columns:
    world_KOLimb_Pos = np.array([df_Observers['KO_posW_tx'], df_Observers['KO_posW_ty'], df_Observers['KO_posW_tz']]).T
    world_KOLimb_Ori_R = R.from_quat(df_Observers[["KO_posW_qx", "KO_posW_qy", "KO_posW_qz", "KO_posW_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_KOLimb_Ori_R = world_KOLimb_Ori_R.inv()
    alignedPoses["KO"] =  compute_aligned_pose(
        world_KOLimb_Pos, 
        world_KOLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_KOLimb_Ori_quat = alignedPoses["KO"]["aligned_orientation"].as_quat()
    df_Observers['KO_posW_tx'] = alignedPoses["KO"]["aligned_position"][:,0]
    df_Observers['KO_posW_ty'] = alignedPoses["KO"]["aligned_position"][:,1]
    df_Observers['KO_posW_tz'] = alignedPoses["KO"]["aligned_position"][:,2]
    df_Observers['KO_posW_qx'] = new_world_KOLimb_Ori_quat[:,0]
    df_Observers['KO_posW_qy'] = new_world_KOLimb_Ori_quat[:,1]
    df_Observers['KO_posW_qz'] = new_world_KOLimb_Ori_quat[:,2]
    df_Observers['KO_posW_qw'] = new_world_KOLimb_Ori_quat[:,3]
if 'KO_APC_posW_tx' in df_Observers.columns:
    world_KO_APCLimb_Pos = np.array([df_Observers['KO_APC_posW_tx'], df_Observers['KO_APC_posW_ty'], df_Observers['KO_APC_posW_tz']]).T
    world_KO_APCLimb_Ori_R = R.from_quat(df_Observers[["KO_APC_posW_qx", "KO_APC_posW_qy", "KO_APC_posW_qz", "KO_APC_posW_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_KO_APCLimb_Ori_R = world_KO_APCLimb_Ori_R.inv()
    alignedPoses["KO_APC"] =  compute_aligned_pose(
        world_KO_APCLimb_Pos, 
        world_KO_APCLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_KO_APCLimb_Ori_quat = alignedPoses["KO_APC"]["aligned_orientation"].as_quat()
    df_Observers['KO_APC_posW_tx'] = alignedPoses["KO_APC"]["aligned_position"][:,0]
    df_Observers['KO_APC_posW_ty'] = alignedPoses["KO_APC"]["aligned_position"][:,1]
    df_Observers['KO_APC_posW_tz'] = alignedPoses["KO_APC"]["aligned_position"][:,2]
    df_Observers['KO_APC_posW_qx'] = new_world_KO_APCLimb_Ori_quat[:,0]
    df_Observers['KO_APC_posW_qy'] = new_world_KO_APCLimb_Ori_quat[:,1]
    df_Observers['KO_APC_posW_qz'] = new_world_KO_APCLimb_Ori_quat[:,2]
    df_Observers['KO_APC_posW_qw'] = new_world_KO_APCLimb_Ori_quat[:,3]
if 'KO_ASC_posW_tx' in df_Observers.columns:
    world_KO_ASCLimb_Pos = np.array([df_Observers['KO_ASC_posW_tx'], df_Observers['KO_ASC_posW_ty'], df_Observers['KO_ASC_posW_tz']]).T
    world_KO_ASCLimb_Ori_R = R.from_quat(df_Observers[["KO_ASC_posW_qx", "KO_ASC_posW_qy", "KO_ASC_posW_qz", "KO_ASC_posW_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_KO_ASCLimb_Ori_R = world_KO_ASCLimb_Ori_R.inv()
    alignedPoses["KO_ASC"] =  compute_aligned_pose(
        world_KO_ASCLimb_Pos, 
        world_KO_ASCLimb_Ori_R, 
        matchIndex,
        averageInterval
    )
    
    new_world_KO_ASCLimb_Ori_quat = alignedPoses["KO_ASC"]["aligned_orientation"].as_quat()
    df_Observers['KO_ASC_posW_tx'] = alignedPoses["KO_ASC"]["aligned_position"][:,0]
    df_Observers['KO_ASC_posW_ty'] = alignedPoses["KO_ASC"]["aligned_position"][:,1]
    df_Observers['KO_ASC_posW_tz'] = alignedPoses["KO_ASC"]["aligned_position"][:,2]
    df_Observers['KO_ASC_posW_qx'] = new_world_KO_ASCLimb_Ori_quat[:,0]
    df_Observers['KO_ASC_posW_qy'] = new_world_KO_ASCLimb_Ori_quat[:,1]
    df_Observers['KO_ASC_posW_qz'] = new_world_KO_ASCLimb_Ori_quat[:,2]
    df_Observers['KO_ASC_posW_qw'] = new_world_KO_ASCLimb_Ori_quat[:,3]
if 'KO_ZPC_posW_tx' in df_Observers.columns:
    world_KO_ZPCLimb_Pos = np.array([df_Observers['KO_ZPC_posW_tx'], df_Observers['KO_ZPC_posW_ty'], df_Observers['KO_ZPC_posW_tz']]).T
    world_KO_ZPCLimb_Ori_R = R.from_quat(df_Observers[["KO_ZPC_posW_qx", "KO_ZPC_posW_qy", "KO_ZPC_posW_qz", "KO_ZPC_posW_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_KO_ZPCLimb_Ori_R = world_KO_ZPCLimb_Ori_R.inv()
    alignedPoses["KO_ZPC"] =  compute_aligned_pose(
        world_KO_ZPCLimb_Pos, 
        world_KO_ZPCLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_KO_ZPCLimb_Ori_quat = alignedPoses["KO_ZPC"]["aligned_orientation"].as_quat()
    df_Observers['KO_ZPC_posW_tx'] = alignedPoses["KO_ZPC"]["aligned_position"][:,0]
    df_Observers['KO_ZPC_posW_ty'] = alignedPoses["KO_ZPC"]["aligned_position"][:,1]
    df_Observers['KO_ZPC_posW_tz'] = alignedPoses["KO_ZPC"]["aligned_position"][:,2]
    df_Observers['KO_ZPC_posW_qx'] = new_world_KO_ZPCLimb_Ori_quat[:,0]
    df_Observers['KO_ZPC_posW_qy'] = new_world_KO_ZPCLimb_Ori_quat[:,1]
    df_Observers['KO_ZPC_posW_qz'] = new_world_KO_ZPCLimb_Ori_quat[:,2]
    df_Observers['KO_ZPC_posW_qw'] = new_world_KO_ZPCLimb_Ori_quat[:,3]

if 'KODisabled_WithProcess_posW_tx' in df_Observers.columns:
    world_KODisabled_WithProcessLimb_Pos = np.array([df_Observers['KODisabled_WithProcess_posW_tx'], df_Observers['KODisabled_WithProcess_posW_ty'], df_Observers['KODisabled_WithProcess_posW_tz']]).T
    world_KODisabled_WithProcessLimb_Ori_R = R.from_quat(df_Observers[["KODisabled_WithProcess_posW_qx", "KODisabled_WithProcess_posW_qy", "KODisabled_WithProcess_posW_qz", "KODisabled_WithProcess_posW_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_KODisabled_WithProcessLimb_Ori_R = world_KODisabled_WithProcessLimb_Ori_R.inv()
    alignedPoses["KODisabled_WithProcess"] =  compute_aligned_pose(
        world_KODisabled_WithProcessLimb_Pos, 
        world_KODisabled_WithProcessLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_KODisabled_WithProcessLimb_Ori_quat = alignedPoses["KODisabled_WithProcess"]["aligned_orientation"].as_quat()
    df_Observers['KODisabled_WithProcess_posW_tx'] = alignedPoses["KODisabled_WithProcess"]["aligned_position"][:,0]
    df_Observers['KODisabled_WithProcess_posW_ty'] = alignedPoses["KODisabled_WithProcess"]["aligned_position"][:,1]
    df_Observers['KODisabled_WithProcess_posW_tz'] = alignedPoses["KODisabled_WithProcess"]["aligned_position"][:,2]
    df_Observers['KODisabled_WithProcess_posW_qx'] = new_world_KODisabled_WithProcessLimb_Ori_quat[:,0]
    df_Observers['KODisabled_WithProcess_posW_qy'] = new_world_KODisabled_WithProcessLimb_Ori_quat[:,1]
    df_Observers['KODisabled_WithProcess_posW_qz'] = new_world_KODisabled_WithProcessLimb_Ori_quat[:,2]
    df_Observers['KODisabled_WithProcess_posW_qw'] = new_world_KODisabled_WithProcessLimb_Ori_quat[:,3]

if 'Vanyte_pose_tx' in df_Observers.columns:
    world_VanyteLimb_Pos = np.array([df_Observers['Vanyte_pose_tx'], df_Observers['Vanyte_pose_ty'], df_Observers['Vanyte_pose_tz']]).T
    world_VanyteLimb_Ori_R = R.from_quat(df_Observers[["Vanyte_pose_qx", "Vanyte_pose_qy", "Vanyte_pose_qz", "Vanyte_pose_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_VanyteLimb_Ori_R = world_VanyteLimb_Ori_R.inv()
    alignedPoses["Vanyte"] =  compute_aligned_pose(
        world_VanyteLimb_Pos, 
        world_VanyteLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_VanyteLimb_Ori_quat = alignedPoses["Vanyte"]["aligned_orientation"].as_quat()
    df_Observers['Vanyte_pose_tx'] = alignedPoses["Vanyte"]["aligned_position"][:,0]
    df_Observers['Vanyte_pose_ty'] = alignedPoses["Vanyte"]["aligned_position"][:,1]
    df_Observers['Vanyte_pose_tz'] = alignedPoses["Vanyte"]["aligned_position"][:,2]
    df_Observers['Vanyte_pose_qx'] = new_world_VanyteLimb_Ori_quat[:,0]
    df_Observers['Vanyte_pose_qy'] = new_world_VanyteLimb_Ori_quat[:,1]
    df_Observers['Vanyte_pose_qz'] = new_world_VanyteLimb_Ori_quat[:,2]
    df_Observers['Vanyte_pose_qw'] = new_world_VanyteLimb_Ori_quat[:,3]
if 'Tilt_pose_tx' in df_Observers.columns:
    world_TiltLimb_Pos = np.array([df_Observers['Tilt_pose_tx'], df_Observers['Tilt_pose_ty'], df_Observers['Tilt_pose_tz']]).T
    world_TiltLimb_Ori_R = R.from_quat(df_Observers[["Tilt_pose_qx", "Tilt_pose_qy", "Tilt_pose_qz", "Tilt_pose_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_TiltLimb_Ori_R = world_TiltLimb_Ori_R.inv()
    alignedPoses["Tilt"] =  compute_aligned_pose(
        world_TiltLimb_Pos, 
        world_TiltLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_TiltLimb_Ori_quat = alignedPoses["Tilt"]["aligned_orientation"].as_quat()
    df_Observers['Tilt_pose_tx'] = alignedPoses["Tilt"]["aligned_position"][:,0]
    df_Observers['Tilt_pose_ty'] = alignedPoses["Tilt"]["aligned_position"][:,1]
    df_Observers['Tilt_pose_tz'] = alignedPoses["Tilt"]["aligned_position"][:,2]
    df_Observers['Tilt_pose_qx'] = new_world_TiltLimb_Ori_quat[:,0]
    df_Observers['Tilt_pose_qy'] = new_world_TiltLimb_Ori_quat[:,1]
    df_Observers['Tilt_pose_qz'] = new_world_TiltLimb_Ori_quat[:,2]
    df_Observers['Tilt_pose_qw'] = new_world_TiltLimb_Ori_quat[:,3]
if 'Controller_tx' in df_Observers.columns:
    world_ControllerLimb_Pos = np.array([df_Observers['Controller_tx'], df_Observers['Controller_ty'], df_Observers['Controller_tz']]).T
    world_ControllerLimb_Ori_R = R.from_quat(df_Observers[["Controller_qx", "Controller_qy", "Controller_qz", "Controller_qw"]].values)
    # We get the inverse of the orientation as the inverse quaternion was stored
    world_ControllerLimb_Ori_R = world_ControllerLimb_Ori_R.inv()
    alignedPoses["Controller"] =  compute_aligned_pose(
        world_ControllerLimb_Pos, 
        world_ControllerLimb_Ori_R, 
        matchIndex,
        averageInterval
    )

    new_world_ControllerLimb_Ori_quat = alignedPoses["Controller"]["aligned_orientation"].as_quat()
    df_Observers['Controller_tx'] = alignedPoses["Controller"]["aligned_position"][:,0]
    df_Observers['Controller_ty'] = alignedPoses["Controller"]["aligned_position"][:,1]
    df_Observers['Controller_tz'] = alignedPoses["Controller"]["aligned_position"][:,2]
    df_Observers['Controller_qx'] = new_world_ControllerLimb_Ori_quat[:,0]
    df_Observers['Controller_qy'] = new_world_ControllerLimb_Ori_quat[:,1]
    df_Observers['Controller_qz'] = new_world_ControllerLimb_Ori_quat[:,2]
    df_Observers['Controller_qw'] = new_world_ControllerLimb_Ori_quat[:,3]
if 'Hartley_IMU_Position_x' in df_Observers.columns:
    world_HartleyIMU_Pos = np.array([df_Observers['Hartley_IMU_Position_x'], df_Observers['Hartley_IMU_Position_y'], df_Observers['Hartley_IMU_Position_z']]).T
    world_HartleyIMU_Ori_R = R.from_quat(df_Observers[["Hartley_IMU_Orientation_x", "Hartley_IMU_Orientation_y", "Hartley_IMU_Orientation_z", "Hartley_IMU_Orientation_w"]].values)

    posImuFb = df_Observers[['HartleyIEKF_imuFbKine_position_x', 'HartleyIEKF_imuFbKine_position_y', 'HartleyIEKF_imuFbKine_position_z']].to_numpy()
    quaternions_rImuFb = df_Observers[['HartleyIEKF_imuFbKine_ori_x', 'HartleyIEKF_imuFbKine_ori_y', 'HartleyIEKF_imuFbKine_ori_z', 'HartleyIEKF_imuFbKine_ori_w']].to_numpy()
    rImuFb = R.from_quat(quaternions_rImuFb)

    world_Hartley_Pos = world_HartleyIMU_Pos + world_HartleyIMU_Ori_R.apply(posImuFb)
    world_Hartley_Ori_R = world_HartleyIMU_Ori_R * rImuFb
    alignedPoses["Hartley"] =  compute_aligned_pose(
        world_Hartley_Pos, 
        world_Hartley_Ori_R, 
        matchIndex,
        averageInterval
    )

    
    new_world_Hartley_Ori_quat = alignedPoses["Hartley"]["aligned_orientation"].as_quat()
    df_Observers['Hartley_Position_x'] = alignedPoses["Hartley"]["aligned_position"][:,0]
    df_Observers['Hartley_Position_y'] = alignedPoses["Hartley"]["aligned_position"][:,1]
    df_Observers['Hartley_Position_z'] = alignedPoses["Hartley"]["aligned_position"][:,2]
    df_Observers['Hartley_Orientation_x'] = new_world_Hartley_Ori_quat[:,0]
    df_Observers['Hartley_Orientation_y'] = new_world_Hartley_Ori_quat[:,1]
    df_Observers['Hartley_Orientation_z'] = new_world_Hartley_Ori_quat[:,2]
    df_Observers['Hartley_Orientation_w'] = new_world_Hartley_Ori_quat[:,3]






###############################  Plot of the matched poses  ###############################


if(displayLogs):

    new_world_MocapLimb_Ori_euler = alignedPoses["Mocap"]["aligned_orientation"].as_euler("xyz")
    new_world_MocapLimb_Ori_euler_continuous = continuous_euler(new_world_MocapLimb_Ori_euler)


    figNewPose = go.Figure()

    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_Ori_euler_continuous[:,0], mode='lines', name='world_MocapLimb_Ori_roll'))
    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_Ori_euler_continuous[:,1], mode='lines', name='world_MocapLimb_Ori_pitch'))
    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_Ori_euler_continuous[:,2], mode='lines', name='world_MocapLimb_Ori_yaw'))

    figNewPose.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_euler_continuous"][:,0], mode='lines', name='world_RefObserverLimb_Ori_roll'))
    figNewPose.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_euler_continuous"][:,1], mode='lines', name='world_RefObserverLimb_Ori_pitch'))
    figNewPose.add_trace(go.Scatter(x=df_Observers["t"], y=initPosesAndTransfos["RefObserver"]["ori_euler_continuous"][:,2], mode='lines', name='world_RefObserverLimb_Ori_yaw'))


    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=alignedPoses["Mocap"]["aligned_position"][:,0], mode='lines', name='world_MocapLimb_Pos_x'))
    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=alignedPoses["Mocap"]["aligned_position"][:,1], mode='lines', name='world_MocapLimb_Pos_y'))
    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=alignedPoses["Mocap"]["aligned_position"][:,2], mode='lines', name='world_MocapLimb_Pos_z'))

    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=world_RefObserverLimb_Pos[:,0], mode='lines', name='world_RefObserverLimb_Pos_x'))
    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=world_RefObserverLimb_Pos[:,1], mode='lines', name='world_RefObserverLimb_Pos_y'))
    figNewPose.add_trace(go.Scatter(x=mocapData["t"], y=world_RefObserverLimb_Pos[:,2], mode='lines', name='world_RefObserverLimb_Pos_z'))

    figNewPose.update_layout(title=f"{scriptName}: Pose after matching")

    figNewPose.write_image(f'{path_to_project}/output_data/scriptResults/matchInitPose/spatially_aligned_pos_transfo.png')

    # Show the plotly figure
    figNewPose.show()


    #####################  Orientation and position difference wrt the initial frame  #####################


    new_world_MocapLimb_pos_transfo = alignedPoses["Mocap"]["aligned_orientation"][0].apply(alignedPoses["Mocap"]["aligned_position"] - alignedPoses["Mocap"]["aligned_position"][0], inverse=True)
    world_RefObserverLimb_pos_transfo = world_RefObserverLimb_Ori_R[0].apply(world_RefObserverLimb_Pos - world_RefObserverLimb_Pos[0], inverse=True)

    new_world_MocapLimb_Ori_R_transfo = alignedPoses["Mocap"]["aligned_orientation"][0].inv() * alignedPoses["Mocap"]["aligned_orientation"]
    world_RefObserverLimb_Ori_R_transfo = world_RefObserverLimb_Ori_R[0].inv() * world_RefObserverLimb_Ori_R

    new_world_MocapLimb_Ori_transfo_euler = new_world_MocapLimb_Ori_R_transfo.as_euler("xyz")
    world_RefObserverLimb_Ori_transfo_euler = world_RefObserverLimb_Ori_R_transfo.as_euler("xyz")

    new_world_MocapLimb_Ori_transfo_euler_continuous = continuous_euler(new_world_MocapLimb_Ori_transfo_euler)
    world_RefObserverLimb_Ori_transfo_euler_continuous = continuous_euler(world_RefObserverLimb_Ori_transfo_euler)

    figTransfo = go.Figure()

    figTransfo.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_Ori_transfo_euler_continuous[:,0], mode='lines', name='world_MocapLimb_Ori_transfo_roll'))
    figTransfo.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_Ori_transfo_euler_continuous[:,1], mode='lines', name='world_MocapLimb_Ori_transfo_pitch'))
    figTransfo.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_Ori_transfo_euler_continuous[:,2], mode='lines', name='world_MocapLimb_Ori_transfo_yaw'))

    figTransfo.add_trace(go.Scatter(x=df_Observers["t"], y=world_RefObserverLimb_Ori_transfo_euler_continuous[:,0], mode='lines', name='world_RefObserverLimb_Ori_transfo_roll'))
    figTransfo.add_trace(go.Scatter(x=df_Observers["t"], y=world_RefObserverLimb_Ori_transfo_euler_continuous[:,1], mode='lines', name='world_RefObserverLimb_Ori_transfo_pitch'))
    figTransfo.add_trace(go.Scatter(x=df_Observers["t"], y=world_RefObserverLimb_Ori_transfo_euler_continuous[:,2], mode='lines', name='world_RefObserverLimb_Ori_transfo_yaw'))


    figTransfo.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_pos_transfo[:,0], mode='lines', name='world_MocapLimb_pos_transfo_x'))
    figTransfo.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_pos_transfo[:,1], mode='lines', name='world_MocapLimb_pos_transfo_y'))
    figTransfo.add_trace(go.Scatter(x=mocapData["t"], y=new_world_MocapLimb_pos_transfo[:,2], mode='lines', name='world_MocapLimb_pos_transfo_z'))

    figTransfo.add_trace(go.Scatter(x=df_Observers["t"], y=world_RefObserverLimb_pos_transfo[:,0], mode='lines', name='world_RefObserverLimb_pos_transfo_x'))
    figTransfo.add_trace(go.Scatter(x=df_Observers["t"], y=world_RefObserverLimb_pos_transfo[:,1], mode='lines', name='world_RefObserverLimb_pos_transfo_y'))
    figTransfo.add_trace(go.Scatter(x=df_Observers["t"], y=world_RefObserverLimb_pos_transfo[:,2], mode='lines', name='world_RefObserverLimb_pos_transfo_z'))

    figTransfo.update_layout(title=f"{scriptName}: Transformations after matching")

    figTransfo.write_image(f'{path_to_project}/output_data/scriptResults/matchInitPose/spatially_aligned_ori_transfo.png')

    # Show the plotly figures
    figTransfo.show()





#####################  3D plot of the pose  #####################

if(displayLogs):
    x_min = min((world_MocapLimb_Pos[:,0]).min(), (alignedPoses["Mocap"]["aligned_position"][:,0]).min(), (world_RefObserverLimb_Pos[:,0]).min())
    y_min = min((world_MocapLimb_Pos[:,1]).min(), (alignedPoses["Mocap"]["aligned_position"][:,1]).min(), (world_RefObserverLimb_Pos[:,1]).min())
    z_min = min((world_MocapLimb_Pos[:,2]).min(), (alignedPoses["Mocap"]["aligned_position"][:,2]).min(), (world_RefObserverLimb_Pos[:,2]).min())
    x_min = x_min - np.abs(x_min*0.2)
    y_min = y_min - np.abs(y_min*0.2)
    z_min = z_min - np.abs(z_min*0.2)

    x_max = max((world_MocapLimb_Pos[:,0]).max(), (alignedPoses["Mocap"]["aligned_position"][:,0]).max(), (world_RefObserverLimb_Pos[:,0]).max())
    y_max = max((world_MocapLimb_Pos[:,1]).max(), (alignedPoses["Mocap"]["aligned_position"][:,1]).max(), (world_RefObserverLimb_Pos[:,1]).max())
    z_max = max((world_MocapLimb_Pos[:,2]).max(), (alignedPoses["Mocap"]["aligned_position"][:,2]).max(), (world_RefObserverLimb_Pos[:,2]).max())
    x_max = x_max + np.abs(x_max*0.2)
    y_max = y_max + np.abs(y_max*0.2)
    z_max = z_max + np.abs(z_max*0.2)


    fig = go.Figure()

    # Add traces
    fig.add_trace(go.Scatter3d(
        x=world_MocapLimb_Pos[:,0], 
        y=world_MocapLimb_Pos[:,1], 
        z=world_MocapLimb_Pos[:,2],
        mode='lines',
        line=dict(color='darkblue'),
        name='world_MocapLimb_Pos'
    ))

    fig.add_trace(go.Scatter3d(
        x=alignedPoses["Mocap"]["aligned_position"][:,0], 
        y=alignedPoses["Mocap"]["aligned_position"][:,1], 
        z=alignedPoses["Mocap"]["aligned_position"][:,2],
        mode='lines',
        line=dict(color='darkred'),
        name='new_world_MocapLimb_Pos'
    ))

    fig.add_trace(go.Scatter3d(
        x=world_RefObserverLimb_Pos[:,0], 
        y=world_RefObserverLimb_Pos[:,1], 
        z=world_RefObserverLimb_Pos[:,2],
        mode='lines',
        line=dict(color='darkgreen'),
        name='world_RefObserverLimb_Pos'
    ))

    # Add big points at the initial positions
    fig.add_trace(go.Scatter3d(
        x=[world_MocapLimb_Pos[0,0]], 
        y=[world_MocapLimb_Pos[0,1]], 
        z=[world_MocapLimb_Pos[0,2]],
        mode='markers',
        marker=dict(size=5, color='darkblue'),
        name='Start world_MocapLimb_Pos'
    ))

    fig.add_trace(go.Scatter3d(
        x=[alignedPoses["Mocap"]["aligned_position"][0,0]], 
        y=[alignedPoses["Mocap"]["aligned_position"][0,1]], 
        z=[alignedPoses["Mocap"]["aligned_position"][0,2]],
        mode='markers',
        marker=dict(size=5, color='darkred'),
        name='Start new_world_MocapLimb_Pos'
    ))

    fig.add_trace(go.Scatter3d(
        x=[world_RefObserverLimb_Pos[0,0]], 
        y=[world_RefObserverLimb_Pos[0,1]], 
        z=[world_RefObserverLimb_Pos[0,2]],
        mode='markers',
        marker=dict(size=5, color='darkgreen'),
        name='Start world_RefObserverLimb_Pos'
    ))

    # Add a big point at the matching time
    fig.add_trace(go.Scatter3d(
        x=[alignedPoses["Mocap"]["aligned_position"][matchIndex,0]], 
        y=[alignedPoses["Mocap"]["aligned_position"][matchIndex,1]], 
        z=[alignedPoses["Mocap"]["aligned_position"][matchIndex,2]],
        mode='markers',
        marker=dict(size=5, color='darkorange'),
        name='Matching pose'
    ))

    # Update layout
    fig.update_layout(
        scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z',
            xaxis=dict(range=[x_min, x_max]),
            yaxis=dict(range=[y_min, y_max]),
            zaxis=dict(range=[z_min, z_max]),
            aspectmode='data'
        ),
        legend=dict(
            x=0,
            y=1
        )
        , title=f"{scriptName}: 3D trajectory after matching"
    )

    # Show the plot
    fig.show()



# Save the DataFrame to a new CSV file
if(len(sys.argv) > 3):
    save_csv = sys.argv[3].lower()
else:
    save_csv = input("Do you want to save the data as a CSV file? (y/n): ")
    save_csv = save_csv.lower()


if save_csv == 'y':
    mocapData.to_csv(f'{path_to_project}/output_data/resultMocapLimbData.csv', index=False, sep=';')
    df_Observers.to_csv(f'{path_to_project}/output_data/observerResultsCSV.csv', index=False, sep=';')
    print("Output CSV file has been saved to observerResultsCSV.csv")
else:
    print("Data not saved.")


