import math
import pickle
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.spatial.transform import Rotation as R


from scipy.signal import butter,filtfilt


import os.path


###############################  Main variables initialization  ###############################


displayLogs = True
writeFormattedData = False

withKO = False
withKO_APC = False
withKO_ASC = False
withKO_Disabled = False
withVanyte = False
withTilt = False
withMocap = False
withController = False
withHartley = False

path_to_project = ".."
scriptName = "finalResults"


if(len(sys.argv) > 1):
    timeStepInput = sys.argv[1]
    if(len(sys.argv) > 2):
        displayLogs = sys.argv[2].lower() == 'true'
    if(len(sys.argv) > 3):
        path_to_project = sys.argv[3]
    if(len(sys.argv) > 4):
        writeFormattedData = sys.argv[4].lower() == 'true'
else:
    timeStepInput = input("Please enter the timestep of the controller in milliseconds: ")

try:
    # Check if the timestep was given in milliseconds
    if(timeStepInput.isdigit()):
        timeStep_ms = int(timeStepInput)
        timeStep_s = float(timeStep_ms)/1000.0
    else:
        timeStep_s = float(timeStepInput)
        timeStep_ms = int(timeStep_s*1000.0)
    resample_str = f'{timeStep_ms}ms'
except ValueError:
    print(f"The input timestep is not valid: {timeStepInput}")
    sys.exit(1)

# Read the CSV file into a DataFrame

dfObservers = pd.read_csv(f'{path_to_project}/output_data/observerResultsCSV.csv', delimiter=';')


if 'KO_posW_tx' in dfObservers.columns:
    withKO = True
if 'KO_APC_posW_tx' in dfObservers.columns:
    withKO_APC = True
if 'KO_ASC_posW_tx' in dfObservers.columns:
    withKO_ASC = True
if 'KO_Disabled_posW_tx' in dfObservers.columns:
    withKO_Disabled = True
if 'Vanyte_pose_tx' in dfObservers.columns:
    withVanyte = True
if 'Tilt_pose_tx' in dfObservers.columns:
    withTilt = True
if 'Mocap_pos_x' in dfObservers.columns:
    withMocap = True
if 'Controller_tx' in dfObservers.columns:
    withController = True
if 'Hartley_Position_x' in dfObservers.columns:
    withHartley = True

###############################  Definition  ###############################

def continuous_euler(angles):
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


###############################  Plots  ###############################


if(withMocap):
    dfObservers_overlap = dfObservers[dfObservers["Mocap_datasOverlapping"] == "Datas overlap"]
    df_mocap_toIgnore = dfObservers[dfObservers["Mocap_datasOverlapping"] != "Datas overlap"]

    posMocap_overlap = dfObservers_overlap[['Mocap_pos_x', 'Mocap_pos_y', 'Mocap_pos_z']].to_numpy()
    quaternionsMocap_overlap = dfObservers_overlap[['Mocap_ori_x', 'Mocap_ori_y', 'Mocap_ori_z', 'Mocap_ori_w']].to_numpy()
    rMocap_overlap = R.from_quat(quaternionsMocap_overlap)
    euler_angles_Mocap_overlap = rMocap_overlap.as_euler('xyz')
    euler_angles_Mocap_overlap = continuous_euler(euler_angles_Mocap_overlap)

    if(writeFormattedData):
        dfMocapPose = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfMocapPose['timestamp'] = dfObservers_overlap['t']
        dfMocapPose['tx'] = posMocap_overlap[:,0]
        dfMocapPose['ty'] = posMocap_overlap[:,1]
        dfMocapPose['tz'] = posMocap_overlap[:,2]
        dfMocapPose['qx'] = quaternionsMocap_overlap[:,0]
        dfMocapPose['qy'] = quaternionsMocap_overlap[:,1]
        dfMocapPose['qz'] = quaternionsMocap_overlap[:,2]
        dfMocapPose['qw'] = quaternionsMocap_overlap[:,3]

        dfMocapPose = dfMocapPose[dfObservers["Mocap_datasOverlapping"] == "Datas overlap"]

        txtOutput = f'{path_to_project}/output_data/formattedMocap_Traj.txt'
        dfMocapPose.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 

        d = {'x': posMocap_overlap[:, 0], 'y': posMocap_overlap[:, 1], 'z': posMocap_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/mocap_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)

    if(len(df_mocap_toIgnore) > 0):
        posMocap_mocap_toIgnore = df_mocap_toIgnore[['Mocap_pos_x', 'Mocap_pos_y', 'Mocap_pos_z']].to_numpy()
        quaternionsMocap_mocap_toIgnore = df_mocap_toIgnore[['Mocap_ori_x', 'Mocap_ori_y', 'Mocap_ori_z', 'Mocap_ori_w']].to_numpy()
        rMocap_mocap_toIgnore = R.from_quat(quaternionsMocap_mocap_toIgnore)
        euler_angles_Mocap_mocap_toIgnore = rMocap_mocap_toIgnore.as_euler('xyz')
        euler_angles_Mocap_mocap_toIgnore = continuous_euler(euler_angles_Mocap_mocap_toIgnore)
        
if(withKO):
    posKO = dfObservers[['KO_posW_tx', 'KO_posW_ty', 'KO_posW_tz']].to_numpy()
    quaternionsKO = dfObservers[['KO_posW_qx', 'KO_posW_qy', 'KO_posW_qz', 'KO_posW_qw']].to_numpy()
    rKO = R.from_quat(quaternionsKO)
    euler_angles_KO = rKO.as_euler('xyz')
    euler_angles_KO = continuous_euler(euler_angles_KO)

    if(withMocap):
        posKO_overlap = dfObservers_overlap[['KO_posW_tx', 'KO_posW_ty', 'KO_posW_tz']].to_numpy()
        quaternionsKO_overlap = dfObservers_overlap[['KO_posW_qx', 'KO_posW_qy', 'KO_posW_qz', 'KO_posW_qw']].to_numpy()
        rKO_overlap = R.from_quat(quaternionsKO_overlap)

    if(writeFormattedData):
        dfKoPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfKoPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfKoPose_overlap['tx'] = posKO_overlap[:,0]
        dfKoPose_overlap['ty'] = posKO_overlap[:,1]
        dfKoPose_overlap['tz'] = posKO_overlap[:,2]
        dfKoPose_overlap['qx'] = quaternionsKO_overlap[:,0]
        dfKoPose_overlap['qy'] = quaternionsKO_overlap[:,1]
        dfKoPose_overlap['qz'] = quaternionsKO_overlap[:,2]
        dfKoPose_overlap['qw'] = quaternionsKO_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedKineticsObserver_Traj.txt'
        dfKoPose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 

        d = {'x': posKO_overlap[:, 0], 'y': posKO_overlap[:, 1], 'z': posKO_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/KineticsObserver_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)


if(withKO_APC):
    posKO_APC = dfObservers[['KO_APC_posW_tx', 'KO_APC_posW_ty', 'KO_APC_posW_tz']].to_numpy()
    quaternionsKO_APC = dfObservers[['KO_APC_posW_qx', 'KO_APC_posW_qy', 'KO_APC_posW_qz', 'KO_APC_posW_qw']].to_numpy()
    rKO_APC = R.from_quat(quaternionsKO_APC)
    euler_angles_KO_APC = rKO_APC.as_euler('xyz')
    euler_angles_KO_APC = continuous_euler(euler_angles_KO_APC)

    if(withMocap):
        posKO_APC_overlap = dfObservers_overlap[['KO_APC_posW_tx', 'KO_APC_posW_ty', 'KO_APC_posW_tz']].to_numpy()
        quaternionsKO_APC_overlap = dfObservers_overlap[['KO_APC_posW_qx', 'KO_APC_posW_qy', 'KO_APC_posW_qz', 'KO_APC_posW_qw']].to_numpy()
        rKO_APC_overlap = R.from_quat(quaternionsKO_APC_overlap)

    if(writeFormattedData):
        dfKO_APCPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfKO_APCPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfKO_APCPose_overlap['tx'] = posKO_APC_overlap[:,0]
        dfKO_APCPose_overlap['ty'] = posKO_APC_overlap[:,1]
        dfKO_APCPose_overlap['tz'] = posKO_APC_overlap[:,2]
        dfKO_APCPose_overlap['qx'] = quaternionsKO_APC_overlap[:,0]
        dfKO_APCPose_overlap['qy'] = quaternionsKO_APC_overlap[:,1]
        dfKO_APCPose_overlap['qz'] = quaternionsKO_APC_overlap[:,2]
        dfKO_APCPose_overlap['qw'] = quaternionsKO_APC_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedKO_APC_Traj.txt'
        dfKO_APCPose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 

        d = {'x': posKO_APC_overlap[:, 0], 'y': posKO_APC_overlap[:, 1], 'z': posKO_APC_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/KO_APC_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)

if(withKO_ASC):
    posKO_ASC = dfObservers[['KO_ASC_posW_tx', 'KO_ASC_posW_ty', 'KO_ASC_posW_tz']].to_numpy()
    quaternionsKO_ASC = dfObservers[['KO_ASC_posW_qx', 'KO_ASC_posW_qy', 'KO_ASC_posW_qz', 'KO_ASC_posW_qw']].to_numpy()
    rKO_ASC = R.from_quat(quaternionsKO_ASC)
    euler_angles_KO_ASC = rKO_ASC.as_euler('xyz')
    euler_angles_KO_ASC = continuous_euler(euler_angles_KO_ASC)

    if(withMocap):
        posKO_ASC_overlap = dfObservers_overlap[['KO_ASC_posW_tx', 'KO_ASC_posW_ty', 'KO_ASC_posW_tz']].to_numpy()
        quaternionsKO_ASC_overlap = dfObservers_overlap[['KO_ASC_posW_qx', 'KO_ASC_posW_qy', 'KO_ASC_posW_qz', 'KO_ASC_posW_qw']].to_numpy()
        rKO_ASC_overlap = R.from_quat(quaternionsKO_ASC_overlap)

    if(writeFormattedData):
        dfKO_ASCPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfKO_ASCPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfKO_ASCPose_overlap['tx'] = posKO_ASC_overlap[:,0]
        dfKO_ASCPose_overlap['ty'] = posKO_ASC_overlap[:,1]
        dfKO_ASCPose_overlap['tz'] = posKO_ASC_overlap[:,2]
        dfKO_ASCPose_overlap['qx'] = quaternionsKO_ASC_overlap[:,0]
        dfKO_ASCPose_overlap['qy'] = quaternionsKO_ASC_overlap[:,1]
        dfKO_ASCPose_overlap['qz'] = quaternionsKO_ASC_overlap[:,2]
        dfKO_ASCPose_overlap['qw'] = quaternionsKO_ASC_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedKO_ASC_Traj.txt'
        dfKO_ASCPose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 

        d = {'x': posKO_ASC_overlap[:, 0], 'y': posKO_ASC_overlap[:, 1], 'z': posKO_ASC_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/KO_ASC_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)

if(withKO_Disabled):
    posKO_Disabled = dfObservers[['KO_Disabled_posW_tx', 'KO_Disabled_posW_ty', 'KO_Disabled_posW_tz']].to_numpy()
    quaternionsKO_Disabled = dfObservers[['KO_Disabled_posW_qx', 'KO_Disabled_posW_qy', 'KO_Disabled_posW_qz', 'KO_Disabled_posW_qw']].to_numpy()
    rKO_Disabled = R.from_quat(quaternionsKO_Disabled)
    euler_angles_KO_Disabled = rKO_Disabled.as_euler('xyz')
    euler_angles_KO_Disabled = continuous_euler(euler_angles_KO_Disabled)

    if(withMocap):
        posKO_Disabled_overlap = dfObservers_overlap[['KO_Disabled_posW_tx', 'KO_Disabled_posW_ty', 'KO_Disabled_posW_tz']].to_numpy()
        quaternionsKO_Disabled_overlap = dfObservers_overlap[['KO_Disabled_posW_qx', 'KO_Disabled_posW_qy', 'KO_Disabled_posW_qz', 'KO_Disabled_posW_qw']].to_numpy()
        rKO_Disabled_overlap = R.from_quat(quaternionsKO_Disabled_overlap)

    if(writeFormattedData):
        dfKO_DisabledPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfKO_DisabledPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfKO_DisabledPose_overlap['tx'] = posKO_Disabled_overlap[:,0]
        dfKO_DisabledPose_overlap['ty'] = posKO_Disabled_overlap[:,1]
        dfKO_DisabledPose_overlap['tz'] = posKO_Disabled_overlap[:,2]
        dfKO_DisabledPose_overlap['qx'] = quaternionsKO_Disabled_overlap[:,0]
        dfKO_DisabledPose_overlap['qy'] = quaternionsKO_Disabled_overlap[:,1]
        dfKO_DisabledPose_overlap['qz'] = quaternionsKO_Disabled_overlap[:,2]
        dfKO_DisabledPose_overlap['qw'] = quaternionsKO_Disabled_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedKO_Disabled_Traj.txt'
        dfKO_DisabledPose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 

        d = {'x': posKO_Disabled_overlap[:, 0], 'y': posKO_Disabled_overlap[:, 1], 'z': posKO_Disabled_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/KO_Disabled_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)


if(withVanyte):
    posVanyte = dfObservers[['Vanyte_pose_tx', 'Vanyte_pose_ty', 'Vanyte_pose_tz']].to_numpy()
    quaternionsVanyte = dfObservers[['Vanyte_pose_qx', 'Vanyte_pose_qy', 'Vanyte_pose_qz', 'Vanyte_pose_qw']].to_numpy()
    rVanyte = R.from_quat(quaternionsVanyte)
    euler_angles_vanyte = rVanyte.as_euler('xyz')
    euler_angles_vanyte = continuous_euler(euler_angles_vanyte)

    if(withMocap):
        posVanyte_overlap = dfObservers_overlap[['Vanyte_pose_tx', 'Vanyte_pose_ty', 'Vanyte_pose_tz']].to_numpy()
        quaternionsVanyte_overlap = dfObservers_overlap[['Vanyte_pose_qx', 'Vanyte_pose_qy', 'Vanyte_pose_qz', 'Vanyte_pose_qw']].to_numpy()
        rVanyte_overlap = R.from_quat(quaternionsVanyte_overlap)

    if(writeFormattedData):
        dfVanytePose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfVanytePose_overlap['timestamp'] = dfObservers_overlap['t']
        dfVanytePose_overlap['tx'] = posVanyte_overlap[:,0]
        dfVanytePose_overlap['ty'] = posVanyte_overlap[:,1]
        dfVanytePose_overlap['tz'] = posVanyte_overlap[:,2]
        dfVanytePose_overlap['qx'] = quaternionsVanyte_overlap[:,0]
        dfVanytePose_overlap['qy'] = quaternionsVanyte_overlap[:,1]
        dfVanytePose_overlap['qz'] = quaternionsVanyte_overlap[:,2]
        dfVanytePose_overlap['qw'] = quaternionsVanyte_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedVanyte_Traj.txt'
        dfVanytePose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data)

        d = {'x': posVanyte_overlap[:, 0], 'y': posVanyte_overlap[:, 1], 'z': posVanyte_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/Vanyte_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)

if(withTilt):
    posTilt = dfObservers[['Tilt_pose_tx', 'Tilt_pose_ty', 'Tilt_pose_tz']].to_numpy()
    quaternionsTilt = dfObservers[['Tilt_pose_qx', 'Tilt_pose_qy', 'Tilt_pose_qz', 'Tilt_pose_qw']].to_numpy()
    rTilt = R.from_quat(quaternionsTilt)
    euler_angles_Tilt = rTilt.as_euler('xyz')
    euler_angles_Tilt = continuous_euler(euler_angles_Tilt)

    if(withMocap):
        posTilt_overlap = dfObservers_overlap[['Tilt_pose_tx', 'Tilt_pose_ty', 'Tilt_pose_tz']].to_numpy()
        quaternionsTilt_overlap = dfObservers_overlap[['Tilt_pose_qx', 'Tilt_pose_qy', 'Tilt_pose_qz', 'Tilt_pose_qw']].to_numpy()
        rTilt_overlap = R.from_quat(quaternionsTilt_overlap)

    if(writeFormattedData):
        dfTiltPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfTiltPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfTiltPose_overlap['tx'] = posTilt_overlap[:,0]
        dfTiltPose_overlap['ty'] = posTilt_overlap[:,1]
        dfTiltPose_overlap['tz'] = posTilt_overlap[:,2]
        dfTiltPose_overlap['qx'] = quaternionsTilt_overlap[:,0]
        dfTiltPose_overlap['qy'] = quaternionsTilt_overlap[:,1]
        dfTiltPose_overlap['qz'] = quaternionsTilt_overlap[:,2]
        dfTiltPose_overlap['qw'] = quaternionsTilt_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedTilt_Traj.txt'
        dfTiltPose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 
        
        d = {'x': posTilt_overlap[:, 0], 'y': posTilt_overlap[:, 1], 'z': posTilt_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/Tilt_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)

if(withController):
    posController = dfObservers[['Controller_tx', 'Controller_ty', 'Controller_tz']].to_numpy()
    quaternionsController = dfObservers[['Controller_qx', 'Controller_qy', 'Controller_qz', 'Controller_qw']].to_numpy()
    rController = R.from_quat(quaternionsController)
    euler_angles_Controller = rController.as_euler('xyz')
    euler_angles_Controller = continuous_euler(euler_angles_Controller)

    if(withMocap):
        posController_overlap = dfObservers_overlap[['Controller_tx', 'Controller_ty', 'Controller_tz']].to_numpy()
        quaternionsController_overlap = dfObservers_overlap[['Controller_qx', 'Controller_qy', 'Controller_qz', 'Controller_qw']].to_numpy()
        rController_overlap = R.from_quat(quaternionsController_overlap)

    if(writeFormattedData):
        dfControllerPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfControllerPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfControllerPose_overlap['tx'] = posController_overlap[:,0]
        dfControllerPose_overlap['ty'] = posController_overlap[:,1]
        dfControllerPose_overlap['tz'] = posController_overlap[:,2]
        dfControllerPose_overlap['qx'] = quaternionsController_overlap[:,0]
        dfControllerPose_overlap['qy'] = quaternionsController_overlap[:,1]
        dfControllerPose_overlap['qz'] = quaternionsController_overlap[:,2]
        dfControllerPose_overlap['qw'] = quaternionsController_overlap[:,3]

        txtOutput = f'{path_to_project}/output_data/formattedController_Traj.txt'
        dfControllerPose_overlap.to_csv(txtOutput, header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(txtOutput, 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 

        d = {'x': posController_overlap[:, 0], 'y': posController_overlap[:, 1], 'z': posController_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/Controller_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)


if(withHartley):
    # Convert quaternion to Euler angles (roll, pitch, yaw)
    posHartley_fb = dfObservers[['Hartley_Position_x', 'Hartley_Position_y', 'Hartley_Position_z']].to_numpy()
    quaternionsHartley_fb = dfObservers[['Hartley_Orientation_x', 'Hartley_Orientation_y', 'Hartley_Orientation_z', 'Hartley_Orientation_w']].to_numpy()
    rHartley_fb = R.from_quat(quaternionsHartley_fb)

    euler_angles_Hartley = rHartley_fb.as_euler('xyz')
    euler_angles_Hartley = continuous_euler(euler_angles_Hartley)

    if(withMocap):
        posHartley_fb_overlap = dfObservers_overlap[['Hartley_Position_x', 'Hartley_Position_y', 'Hartley_Position_z']].to_numpy()
        quaternionsHartley_fb_overlap = dfObservers_overlap[['Hartley_Orientation_x', 'Hartley_Orientation_y', 'Hartley_Orientation_z', 'Hartley_Orientation_w']].to_numpy()
        rHartley_fb_overlap = R.from_quat(quaternionsHartley_fb_overlap)

        posImuFb_overlap = dfObservers_overlap[['HartleyIEKF_imuFbKine_position_x', 'HartleyIEKF_imuFbKine_position_y', 'HartleyIEKF_imuFbKine_position_z']].to_numpy()
        quaternions_rImuFb_overlap = dfObservers_overlap[['HartleyIEKF_imuFbKine_ori_x', 'HartleyIEKF_imuFbKine_ori_y', 'HartleyIEKF_imuFbKine_ori_z', 'HartleyIEKF_imuFbKine_ori_w']].to_numpy()
        rImuFb_overlap = R.from_quat(quaternions_rImuFb_overlap)

        linVelImuFb_overlap = dfObservers_overlap[['HartleyIEKF_imuFbKine_linVel_x', 'HartleyIEKF_imuFbKine_linVel_y', 'HartleyIEKF_imuFbKine_linVel_z']].to_numpy()
        angVelImuFb_overlap = dfObservers_overlap[['HartleyIEKF_imuFbKine_angVel_x', 'HartleyIEKF_imuFbKine_angVel_y', 'HartleyIEKF_imuFbKine_angVel_z']].to_numpy()
        posFbImu_overlap = - rImuFb_overlap.apply(posImuFb_overlap, inverse=True)
        linVelFbImu_overlap = rImuFb_overlap.apply(np.cross(angVelImuFb_overlap, posImuFb_overlap), inverse=True) - rImuFb_overlap.apply(linVelImuFb_overlap, inverse=True)


    if(writeFormattedData):
        rHartley_fb_quat_overlap = rHartley_fb_overlap.as_quat()

        dfHartleyPose_overlap = pd.DataFrame(columns=['#', 'timestamp', 'tx', 'ty', 'tz', 'qx', 'qy', 'qz', 'qw'])
        dfHartleyPose_overlap['timestamp'] = dfObservers_overlap['t']
        dfHartleyPose_overlap['tx'] = posHartley_fb_overlap[:,0]
        dfHartleyPose_overlap['ty'] = posHartley_fb_overlap[:,1]
        dfHartleyPose_overlap['tz'] = posHartley_fb_overlap[:,2]
        dfHartleyPose_overlap['qx'] = rHartley_fb_quat_overlap[:,0]
        dfHartleyPose_overlap['qy'] = rHartley_fb_quat_overlap[:,1]
        dfHartleyPose_overlap['qz'] = rHartley_fb_quat_overlap[:,2]
        dfHartleyPose_overlap['qw'] = rHartley_fb_quat_overlap[:,3]

        dfHartleyPose_overlap.to_csv(f'{path_to_project}/output_data/formattedHartley_Traj.txt', header=None, index=None, sep=' ')

        line = '# timestamp tx ty tz qx qy qz qw' 
        with open(f'{path_to_project}/output_data/formattedHartley_Traj.txt', 'r+') as file: 
            file_data = file.read() 
            file.seek(0, 0) 
            file.write(line + '\n' + file_data) 
        
        d = {'x': posHartley_fb_overlap[:, 0], 'y': posHartley_fb_overlap[:, 1], 'z': posHartley_fb_overlap[:, 2]}
        with open(f'{path_to_project}/output_data/Hartley_x_y_z_traj.pickle', 'wb') as f:
            pickle.dump(d, f)


if(displayLogs):
    # Create the figure
    fig = go.Figure()


    # Add traces for each plot
    fig.add_trace(go.Scatter(x=dfObservers['t'], y=posHartley_fb[:, 0], mode='lines', name='Hartley_Position_x'))
    fig.add_trace(go.Scatter(x=dfObservers['t'], y=posHartley_fb[:, 1], mode='lines', name='Hartley_Position_y'))
    fig.add_trace(go.Scatter(x=dfObservers['t'], y=posHartley_fb[:, 2], mode='lines', name='Hartley_Position_z'))
    fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Hartley[:, 0], mode='lines', name='Hartley_Roll'))
    fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Hartley[:, 1], mode='lines', name='Hartley_Pitch'))
    fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Hartley[:, 2], mode='lines', name='Hartley_Yaw'))

    if(withVanyte):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posVanyte[:, 0], mode='lines', name='Vanyte_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posVanyte[:, 1], mode='lines', name='Vanyte_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posVanyte[:, 2], mode='lines', name='Vanyte_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_vanyte[:, 0], mode='lines', name='Vanyte_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_vanyte[:, 1], mode='lines', name='Vanyte_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_vanyte[:, 2], mode='lines', name='Vanyte_Yaw'))

    if(withKO):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO[:, 0], mode='lines', name='KineticsObserver_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO[:, 1], mode='lines', name='KineticsObserver_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO[:, 2], mode='lines', name='KineticsObserver_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO[:, 0], mode='lines', name='KineticsObserver_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO[:, 1], mode='lines', name='KineticsObserver_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO[:, 2], mode='lines', name='KineticsObserver_Yaw'))

    if(withKO_APC):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_APC[:, 0], mode='lines', name='KO_APC_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_APC[:, 1], mode='lines', name='KO_APC_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_APC[:, 2], mode='lines', name='KO_APC_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_APC[:, 0], mode='lines', name='KO_APC_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_APC[:, 1], mode='lines', name='KO_APC_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_APC[:, 2], mode='lines', name='KO_APC_Yaw'))

    if(withKO_ASC):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_ASC[:, 0], mode='lines', name='KO_ASC_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_ASC[:, 1], mode='lines', name='KO_ASC_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_ASC[:, 2], mode='lines', name='KO_ASC_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_ASC[:, 0], mode='lines', name='KO_ASC_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_ASC[:, 1], mode='lines', name='KO_ASC_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_ASC[:, 2], mode='lines', name='KO_ASC_Yaw'))

    if(withKO_Disabled):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_Disabled[:, 0], mode='lines', name='KO_Disabled_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_Disabled[:, 1], mode='lines', name='KO_Disabled_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posKO_Disabled[:, 2], mode='lines', name='KO_Disabled_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_Disabled[:, 0], mode='lines', name='KO_Disabled_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_Disabled[:, 1], mode='lines', name='KO_Disabled_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_KO_Disabled[:, 2], mode='lines', name='KO_Disabled_Yaw'))
        
    if(withTilt):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posTilt[:, 0], mode='lines', name='Tilt_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posTilt[:, 1], mode='lines', name='Tilt_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posTilt[:, 2], mode='lines', name='Tilt_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Tilt[:, 0], mode='lines', name='Tilt_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Tilt[:, 1], mode='lines', name='Tilt_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Tilt[:, 2], mode='lines', name='Tilt_Yaw'))

    if(withMocap):
        fig.add_trace(go.Scatter(x=dfObservers_overlap['t'], y=posMocap_overlap[:, 0], mode='lines', name='Mocap_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers_overlap['t'], y=posMocap_overlap[:, 1], mode='lines', name='Mocap_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers_overlap['t'], y=posMocap_overlap[:, 2], mode='lines', name='Mocap_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers_overlap['t'], y=euler_angles_Mocap_overlap[:, 0], mode='lines', name='Mocap_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers_overlap['t'], y=euler_angles_Mocap_overlap[:, 1], mode='lines', name='Mocap_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers_overlap['t'], y=euler_angles_Mocap_overlap[:, 2], mode='lines', name='Mocap_Yaw'))

        if(len(df_mocap_toIgnore) > 0):
            fig.add_trace(go.Scatter(x=dfObservers['t'], y=posMocap_mocap_toIgnore[:, 0], mode='lines', name='Mocap_mocap_toIgnore_Position_x'))
            fig.add_trace(go.Scatter(x=dfObservers['t'], y=posMocap_mocap_toIgnore[:, 1], mode='lines', name='Mocap_mocap_toIgnore_Position_y'))
            fig.add_trace(go.Scatter(x=dfObservers['t'], y=posMocap_mocap_toIgnore[:, 2], mode='lines', name='Mocap_mocap_toIgnore_Position_z'))
            fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Mocap_mocap_toIgnore[:, 0], mode='lines', name='Mocap_mocap_toIgnore_Roll'))
            fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Mocap_mocap_toIgnore[:, 1], mode='lines', name='Mocap_mocap_toIgnore_Pitch'))
            fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Mocap_mocap_toIgnore[:, 2], mode='lines', name='Mocap_mocap_toIgnore_Yaw'))

    if(withController):
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posController[:, 0], mode='lines', name='Controller_Position_x'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posController[:, 1], mode='lines', name='Controller_Position_y'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=posController[:, 2], mode='lines', name='Controller_Position_z'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Controller[:, 0], mode='lines', name='Controller_Roll'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Controller[:, 1], mode='lines', name='Controller_Pitch'))
        fig.add_trace(go.Scatter(x=dfObservers['t'], y=euler_angles_Controller[:, 2], mode='lines', name='Controller_Yaw'))


    # Update layout
    fig.update_layout(
        title= f'{scriptName}: Pose over time',
        xaxis_title='Time',
        yaxis_title='Value',
        hovermode='x'
    )
    # Show the interactive plot
    fig.show()


    fig2 = go.Figure()

    if(withVanyte):
        fig2.add_trace(go.Scatter(x=posVanyte[:, 0], y=posVanyte[:, 1], mode='lines', name='Vanyte_2dMotion_xy'))
    if(withKO):
        fig2.add_trace(go.Scatter(x=posKO[:, 0], y=posKO[:, 1], mode='lines', name='KineticsObserver_2dMotion_xy'))
    if(withKO_APC):
        fig2.add_trace(go.Scatter(x=posKO_APC[:, 0], y=posKO_APC[:, 1], mode='lines', name='KO_APC_2dMotion_xy'))
    if(withKO_ASC):
        fig2.add_trace(go.Scatter(x=posKO_ASC[:, 0], y=posKO_ASC[:, 1], mode='lines', name='KO_ASC_2dMotion_xy'))
    if(withKO_Disabled):
        fig2.add_trace(go.Scatter(x=posKO_Disabled[:, 0], y=posKO_Disabled[:, 1], mode='lines', name='KODisabled_2dMotion_xy'))

    if(withTilt):
        fig2.add_trace(go.Scatter(x=posTilt[:, 0], y=posTilt[:, 1], mode='lines', name='Tilt_2dMotion_xy'))
    if(withMocap):
        fig2.add_trace(go.Scatter(x=posMocap_overlap[:, 0], y=posMocap_overlap[:, 1], mode='lines', name='Mocap_2dMotion_xy'))
        if(len(df_mocap_toIgnore) > 0):
            fig2.add_trace(go.Scatter(x=posMocap_mocap_toIgnore[:, 0], y=posMocap_mocap_toIgnore[:, 1], mode='lines', name='Mocap_mocap_toIgnore_2dMotion_xy'))
    if(withController):
        fig2.add_trace(go.Scatter(x=posController[:, 0], y=posController[:, 1], mode='lines', name='Controller_2dMotion_xy'))
    fig2.add_trace(go.Scatter(x=posHartley_fb[:,0], y=posHartley_fb[:,1], mode='lines', name='Hartley_2dMotion_xy'))

    # Update layout
    fig2.update_layout(
        xaxis_title='x',
        yaxis_title='y',
        hovermode='x',
        title=f"{scriptName}: 2D trajectories"
    )
    fig2.update_yaxes(
        scaleanchor="x",
        scaleratio=1,
    )
    # Show the interactive plot
    fig2.show()


    fig3 = go.Figure()

    # Get the last time in dfObservers['t']
    last_time = dfObservers['t'].max()

    # Filter the data for the first 3 seconds
    df_first_3s = dfObservers[(dfObservers['t'] >= 0) & (dfObservers['t'] <= 3)]

    # Compute the average bias over the first 3 seconds
    average_bias_x_3 = df_first_3s['Accelerometer_angularVelocity_x'].mean()
    average_bias_x_tuple_3 = tuple(average_bias_x_3 for _ in range(len(dfObservers)))
    average_bias_y_3 = df_first_3s['Accelerometer_angularVelocity_y'].mean()
    average_bias_y_tuple_3 = tuple(average_bias_y_3 for _ in range(len(dfObservers)))
    average_bias_z_3 = df_first_3s['Accelerometer_angularVelocity_z'].mean()
    average_bias_z_tuple_3 = tuple(average_bias_z_3 for _ in range(len(dfObservers)))

    # Filter the data for the last 3 seconds
    df_last_3s = dfObservers[(dfObservers['t'] >= last_time - 3) & (dfObservers['t'] <= last_time)]

    # Compute the average bias over the last 3 seconds
    average_bias_x_last = df_last_3s['Accelerometer_angularVelocity_x'].mean()
    average_bias_x_tuple_last = tuple(average_bias_x_last for _ in range(len(dfObservers)))
    average_bias_y_last = df_last_3s['Accelerometer_angularVelocity_y'].mean()
    average_bias_y_tuple_last = tuple(average_bias_y_last for _ in range(len(dfObservers)))
    average_bias_z_last = df_last_3s['Accelerometer_angularVelocity_z'].mean()
    average_bias_z_tuple_last = tuple(average_bias_z_last for _ in range(len(dfObservers)))

    # Plotting the original data and the computed biases
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['Accelerometer_angularVelocity_x'], mode='lines', name='measured_angVel_x'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['Accelerometer_angularVelocity_y'], mode='lines', name='measured_angVel_y'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['Accelerometer_angularVelocity_z'], mode='lines', name='measured_angVel_z'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=average_bias_x_tuple_3, mode='lines', name='measured_GyroBias_beginning_x'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=average_bias_y_tuple_3, mode='lines', name='measured_GyroBias_beginning_y'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=average_bias_z_tuple_3, mode='lines', name='measured_GyroBias_beginning_z'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=average_bias_x_tuple_last, mode='lines', name='measured_GyroBias_end_x'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=average_bias_y_tuple_last, mode='lines', name='measured_GyroBias_end_y'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=average_bias_z_tuple_last, mode='lines', name='measured_GyroBias_end_z'))

    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['Hartley_IMU_GyroBias_x'], mode='lines', name='Hartley_GyroBias_x'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['Hartley_IMU_GyroBias_y'], mode='lines', name='Hartley_GyroBias_y'))
    fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['Hartley_IMU_GyroBias_z'], mode='lines', name='Hartley_GyroBias_z'))
    if(withKO):
        fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['KoState_gyroBias_Accelerometer_x'], mode='lines', name='KO_GyroBias_x'))
        fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['KoState_gyroBias_Accelerometer_y'], mode='lines', name='KO_GyroBias_y'))
        fig3.add_trace(go.Scatter(x=dfObservers['t'], y=dfObservers['KoState_gyroBias_Accelerometer_z'], mode='lines', name='KO_GyroBias_z'))


    # Update layout
    fig3.update_layout(
        title='Gyrometer biases',
        xaxis_title='x',
        yaxis_title='y',
        hovermode='x'
    )

    # Show the interactive plot
    fig3.show()




    x_min = min((posHartley_fb[:,0]).min(), (posHartley_fb[:,0]).min(), (posHartley_fb[:,0]).min())
    y_min = min((posHartley_fb[:,1]).min(), (posHartley_fb[:,1]).min(), (posHartley_fb[:,1]).min())
    z_min = min((posHartley_fb[:,2]).min(), (posHartley_fb[:,2]).min(), (posHartley_fb[:,2]).min())

    x_max = max((posHartley_fb[:,0]).max(), (posHartley_fb[:,0]).max(), (posHartley_fb[:,0]).max())
    y_max = max((posHartley_fb[:,1]).max(), (posHartley_fb[:,1]).max(), (posHartley_fb[:,1]).max())
    z_max = max((posHartley_fb[:,2]).max(), (posHartley_fb[:,2]).max(), (posHartley_fb[:,2]).max())

    fig3d = go.Figure()

    # Add traces
    fig3d.add_trace(go.Scatter3d(
        x=posHartley_fb[:,0], 
        y=posHartley_fb[:,1], 
        z=posHartley_fb[:,2],
        mode='lines',
        line=dict(color='darkred'),
        name='Hartley'
    ))

    if(withVanyte):
        x_min = min(x_min, (posVanyte[:,0]).min())
        y_min = min(y_min, (posVanyte[:,1]).min())
        z_min = min(z_min, (posVanyte[:,2]).min())

        x_max = max(x_max, (posVanyte[:,0]).max())
        y_max = max(y_max, (posVanyte[:,1]).max())
        z_max = max(z_max, (posVanyte[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posVanyte[:,0], 
            y=posVanyte[:,1], 
            z=posVanyte[:,2],
            mode='lines',
            line=dict(color='darkblue'),
            name='Vanyt-e'
        ))

    if(withKO):
        x_min = min(x_min, (posKO[:,0]).min())
        y_min = min(y_min, (posKO[:,1]).min())
        z_min = min(z_min, (posKO[:,2]).min())

        x_max = max(x_max, (posKO[:,0]).max())
        y_max = max(y_max, (posKO[:,1]).max())
        z_max = max(z_max, (posKO[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posKO[:,0], 
            y=posKO[:,1], 
            z=posKO[:,2],
            mode='lines',
            line=dict(color='darkgreen'),
            name='Kinetics Observer'
        ))
    if(withKO_APC):
        x_min = min(x_min, (posKO_APC[:,0]).min())
        y_min = min(y_min, (posKO_APC[:,1]).min())
        z_min = min(z_min, (posKO_APC[:,2]).min())

        x_max = max(x_max, (posKO_APC[:,0]).max())
        y_max = max(y_max, (posKO_APC[:,1]).max())
        z_max = max(z_max, (posKO_APC[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posKO_APC[:,0], 
            y=posKO_APC[:,1], 
            z=posKO_APC[:,2],
            mode='lines',
            line=dict(color='darkgreen'),
            name='Kinetics Observer APC'
        ))
        
    if(withKO_ASC):
        x_min = min(x_min, (posKO_ASC[:,0]).min())
        y_min = min(y_min, (posKO_ASC[:,1]).min())
        z_min = min(z_min, (posKO_ASC[:,2]).min())

        x_max = max(x_max, (posKO_ASC[:,0]).max())
        y_max = max(y_max, (posKO_ASC[:,1]).max())
        z_max = max(z_max, (posKO_ASC[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posKO_ASC[:,0], 
            y=posKO_ASC[:,1], 
            z=posKO_ASC[:,2],
            mode='lines',
            line=dict(color='darkgreen'),
            name='Kinetics Observer ASC'
        ))

    if(withKO_Disabled):
        x_min = min(x_min, (posKO_Disabled[:,0]).min())
        y_min = min(y_min, (posKO_Disabled[:,1]).min())
        z_min = min(z_min, (posKO_Disabled[:,2]).min())

        x_max = max(x_max, (posKO_Disabled[:,0]).max())
        y_max = max(y_max, (posKO_Disabled[:,1]).max())
        z_max = max(z_max, (posKO_Disabled[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posKO_Disabled[:,0], 
            y=posKO_Disabled[:,1], 
            z=posKO_Disabled[:,2],
            mode='lines',
            line=dict(color='darkgreen'),
            name='Kinetics Observer Disabled'
        ))

    if(withTilt):
        x_min = min(x_min, (posTilt[:,0]).min())
        y_min = min(y_min, (posTilt[:,1]).min())
        z_min = min(z_min, (posTilt[:,2]).min())

        x_max = max(x_max, (posTilt[:,0]).max())
        y_max = max(y_max, (posTilt[:,1]).max())
        z_max = max(z_max, (posTilt[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posTilt[:,0], 
            y=posTilt[:,1], 
            z=posTilt[:,2],
            mode='lines',
            line=dict(color='darkcyan'),
            name='Tilt Observer'
        ))

    if(withMocap):
        x_min = min(x_min, (posMocap_overlap[:,0]).min())
        y_min = min(y_min, (posMocap_overlap[:,1]).min())
        z_min = min(z_min, (posMocap_overlap[:,2]).min())

        x_max = max(x_max, (posMocap_overlap[:,0]).max())
        y_max = max(y_max, (posMocap_overlap[:,1]).max())
        z_max = max(z_max, (posMocap_overlap[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posMocap_overlap[:,0], 
            y=posMocap_overlap[:,1], 
            z=posMocap_overlap[:,2],
            mode='lines',
            line=dict(color='darkviolet'),
            name='Motion capture'
        ))
        
        if(len(df_mocap_toIgnore) > 0):
            x_min = min(x_min, (posMocap_mocap_toIgnore[:,0]).min())
            y_min = min(y_min, (posMocap_mocap_toIgnore[:,1]).min())
            z_min = min(z_min, (posMocap_mocap_toIgnore[:,2]).min())

            x_max = max(x_max, (posMocap_mocap_toIgnore[:,0]).max())
            y_max = max(y_max, (posMocap_mocap_toIgnore[:,1]).max())
            z_max = max(z_max, (posMocap_mocap_toIgnore[:,2]).max())

            fig3d.add_trace(go.Scatter3d(
                x=posMocap_mocap_toIgnore[:,0], 
                y=posMocap_mocap_toIgnore[:,1], 
                z=posMocap_mocap_toIgnore[:,2],
                mode='lines',
                line=dict(width=0.5, color='darkviolet'),
                name='Motion capture to ignore'
            ))

    if(withController):
        x_min = min(x_min, (posController[:,0]).min())
        y_min = min(y_min, (posController[:,1]).min())
        z_min = min(z_min, (posController[:,2]).min())

        x_max = max(x_max, (posController[:,0]).max())
        y_max = max(y_max, (posController[:,1]).max())
        z_max = max(z_max, (posController[:,2]).max())

        fig3d.add_trace(go.Scatter3d(
            x=posController[:,0], 
            y=posController[:,1], 
            z=posController[:,2],
            mode='lines',
            line=dict(color='darkorange'),
            name='Controller'
        ))


    x_min = x_min - np.abs(x_min*0.2)
    y_min = y_min - np.abs(y_min*0.2)
    z_min = z_min - np.abs(z_min*0.2)
    x_max = x_max + np.abs(x_max*0.2)
    y_max = y_max + np.abs(y_max*0.2)
    z_max = z_max + np.abs(z_max*0.2)


    # Update layout
    fig3d.update_layout(
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
        , title=f"{scriptName}: 3D trajectories"
    )

    # Show the plot
    fig3d.show()




###############################  Criterias based on the local linear velocity  ###############################

def computeRMSE(ground_truth_data, observer_data, observer_name):
    RMSE = np.sqrt(((observer_data - ground_truth_data) ** 2).mean(axis=0))
    return RMSE

# Function to compute relative error with sign and convert to percentage
def compute_relative_error(data, reference_data):
    relative_error = (np.abs(data) - np.abs(reference_data)) / np.abs(reference_data) * 100
    return relative_error

if(writeFormattedData):
    zeros_row = np.zeros((1, 3))

    if(withMocap):
        rmse_values = {}
        relative_errors = {}
        data = []
        index_labels = []

        posMocap_imu_overlap = posMocap_overlap + rMocap_overlap.apply(posFbImu_overlap)

        velMocap_overlap = np.diff(posMocap_overlap, axis=0)/timeStep_s
        velMocap_overlap = np.vstack((zeros_row,velMocap_overlap))
        locVelMocap_overlap = rMocap_overlap.apply(velMocap_overlap, inverse=True)

        velMocap_imu_overlap = np.diff(posMocap_imu_overlap, axis=0)/timeStep_s
        velMocap_imu_overlap = np.vstack((zeros_row,velMocap_imu_overlap))

        rWorldImuMocap_overlap = rMocap_overlap * rImuFb_overlap.inv()
        locVelMocap_imu_estim = rWorldImuMocap_overlap.apply(velMocap_imu_overlap, inverse=True)
        d = {'llve': {}, 'estimate': {}}
        d['llve'] = {'x': locVelMocap_overlap[:, 0], 'y': locVelMocap_overlap[:, 1], 'z': locVelMocap_overlap[:, 2]}
        d['estimate'] = {'x': locVelMocap_imu_estim[:, 0], 'y': locVelMocap_imu_estim[:, 1], 'z': locVelMocap_imu_estim[:, 2]}
        with open(f'{path_to_project}/output_data/mocap_loc_vel.pickle', 'wb') as f:
            pickle.dump(d, f)


        if(displayLogs):
            figLocLinVels = go.Figure()
            figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelMocap_overlap[:,0], mode='lines', name='locVelMocap_x'))
            figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelMocap_overlap[:,1], mode='lines', name='locVelMocap_y'))
            figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelMocap_overlap[:,2], mode='lines', name='locVelMocap_z'))

            figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=velMocap_imu_overlap[:,0], mode='lines', name='vel_IMUMocap_x'))
            figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=velMocap_imu_overlap[:,1], mode='lines', name='vel_IMUMocap_y'))
            figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=velMocap_imu_overlap[:,2], mode='lines', name='vel_IMUMocap_z'))
            figLocLinVels.update_layout(title=f"{scriptName}: Linear velocities")

        if(withHartley):
            velHartley_overlap = np.diff(posHartley_fb_overlap, axis=0)/timeStep_s
            velHartley_overlap = np.vstack((zeros_row,velHartley_overlap)) # Velocity obtained by finite differences
            locVelHartley_overlap = rHartley_fb_overlap.apply(velHartley_overlap, inverse=True)

            # estimated velocity
            linVelImu_Hartley_overlap = dfObservers_overlap[['Hartley_IMU_Velocity_x', 'Hartley_IMU_Velocity_y', 'Hartley_IMU_Velocity_z']].to_numpy()
            
            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelHartley_overlap[:,0], mode='lines', name='locVelHartley_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelHartley_overlap[:,1], mode='lines', name='locVelHartley_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelHartley_overlap[:,2], mode='lines', name='locVelHartley_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelImu_Hartley_overlap[:,0], mode='lines', name='linVel_IMU_Hartley_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelImu_Hartley_overlap[:,1], mode='lines', name='linVel_IMU_Hartley_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelImu_Hartley_overlap[:,2], mode='lines', name='linVel_IMU_Hartley_z'))
            rmse_values['Hartley'] = computeRMSE(locVelMocap_overlap, locVelHartley_overlap, "Hartley")
            arrays = [
                ['RMSE', 'RMSE', 'RMSE', 'Relative Error to Hartley (%)', 'Relative Error to Hartley (%)', 'Relative Error to Hartley (%)'],
                ['X', 'Y', 'Z', 'X', 'Y', 'Z']
            ]
            index_labels.append('Hartley')
            data.append(np.concatenate([rmse_values['Hartley'], np.zeros_like(rmse_values['Hartley'])]))
            
            rWorldImuHartley_overlap = rHartley_fb_overlap * rImuFb_overlap.inv()

            locVelHartley_imu_estim = rWorldImuHartley_overlap.apply(linVelImu_Hartley_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelHartley_overlap[:, 0], 'y': locVelHartley_overlap[:, 1], 'z': locVelHartley_overlap[:, 2]}
            d['estimate'] = {'x': locVelHartley_imu_estim[:, 0], 'y': locVelHartley_imu_estim[:, 1], 'z': locVelHartley_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/Hartley_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)
        else:
            arrays = [
                ['RMSE', 'RMSE', 'RMSE'],
                ['X', 'Y', 'Z']
            ]

        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples, names=['Metric', 'Axis'])

        if(withKO):
            velKO_overlap = np.diff(posKO_overlap, axis=0)/timeStep_s
            velKO_overlap = np.vstack((zeros_row,velKO_overlap)) # Velocity obtained by finite differences
            locVelKO_overlap = rKO_overlap.apply(velKO_overlap, inverse=True)

            linVelKO_fb_overlap = dfObservers_overlap[['KO_velW_vx', 'KO_velW_vy', 'KO_velW_vz']].to_numpy() # estimated linear velocity
            angVelKO_fb_overlap = dfObservers_overlap[['KO_velW_wx', 'KO_velW_wy', 'KO_velW_wz']].to_numpy() # estimated angular velocity
            linVelKO_imu_overlap = linVelKO_fb_overlap + np.cross(angVelKO_fb_overlap, rKO_overlap.apply(posFbImu_overlap)) + rKO_overlap.apply(linVelFbImu_overlap)

            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_overlap[:,0], mode='lines', name='locVelKO_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_overlap[:,1], mode='lines', name='locVelKO_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_overlap[:,2], mode='lines', name='locVelKO_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_imu_overlap[:,0], mode='lines', name='linVel_IMU__KO_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_imu_overlap[:,1], mode='lines', name='linVel_IMU_KO_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_imu_overlap[:,2], mode='lines', name='linVel_IMU_KO_z'))

            rmse_values['KO'] = computeRMSE(locVelMocap_overlap, locVelKO_overlap, "KO")
            index_labels.append('KO')
            if(withHartley):
                relative_errors['KO'] = compute_relative_error(rmse_values['KO'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['KO'], relative_errors['KO']]))
            else:
                data.append(rmse_values['KO'])

            rWorldImuKO_overlap = rKO_overlap * rImuFb_overlap.inv()
            locVelKO_imu_estim = rWorldImuKO_overlap.apply(linVelKO_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelKO_overlap[:, 0], 'y': locVelKO_overlap[:, 1], 'z': locVelKO_overlap[:, 2]}
            d['estimate'] = {'x': locVelKO_imu_estim[:, 0], 'y': locVelKO_imu_estim[:, 1], 'z': locVelKO_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/KineticsObserver_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)


        if(withKO_APC):
            velKO_APC_overlap = np.diff(posKO_APC_overlap, axis=0)/timeStep_s
            velKO_APC_overlap = np.vstack((zeros_row,velKO_APC_overlap)) # Velocity obtained by finite differences
            locVelKO_APC_overlap = rKO_APC_overlap.apply(velKO_APC_overlap, inverse=True)

            linVelKO_APC_fb_overlap = dfObservers_overlap[['KO_APC_velW_vx', 'KO_APC_velW_vy', 'KO_APC_velW_vz']].to_numpy() # estimated linear velocity
            angVelKO_APC_fb_overlap = dfObservers_overlap[['KO_APC_velW_wx', 'KO_APC_velW_wy', 'KO_APC_velW_wz']].to_numpy() # estimated angular velocity
            linVelKO_APC_imu_overlap = linVelKO_APC_fb_overlap + np.cross(angVelKO_APC_fb_overlap, rKO_APC_overlap.apply(posFbImu_overlap)) + rKO_APC_overlap.apply(linVelFbImu_overlap)

            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_APC_overlap[:,0], mode='lines', name='locVelKO_APC_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_APC_overlap[:,1], mode='lines', name='locVelKO_APC_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_APC_overlap[:,2], mode='lines', name='locVelKO_APC_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_APC_imu_overlap[:,0], mode='lines', name='linVel_IMU__KO_APC_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_APC_imu_overlap[:,1], mode='lines', name='linVel_IMU_KO_APC_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_APC_imu_overlap[:,2], mode='lines', name='linVel_IMU_KO_APC_z'))

            rmse_values['KO_APC'] = computeRMSE(locVelMocap_overlap, locVelKO_APC_overlap, "KO_APC")
            index_labels.append('KO_APC')
            if(withHartley):
                relative_errors['KO_APC'] = compute_relative_error(rmse_values['KO_APC'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['KO_APC'], relative_errors['KO_APC']]))
            else:
                data.append(rmse_values['KO_APC'])

            rWorldImuKO_APC_overlap = rKO_APC_overlap * rImuFb_overlap.inv()
            locVelKO_APC_imu_estim = rWorldImuKO_APC_overlap.apply(linVelKO_APC_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelKO_APC_overlap[:, 0], 'y': locVelKO_APC_overlap[:, 1], 'z': locVelKO_APC_overlap[:, 2]}
            d['estimate'] = {'x': locVelKO_APC_imu_estim[:, 0], 'y': locVelKO_APC_imu_estim[:, 1], 'z': locVelKO_APC_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/KO_APC_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)

        if(withKO_ASC):
            velKO_ASC_overlap = np.diff(posKO_ASC_overlap, axis=0)/timeStep_s
            velKO_ASC_overlap = np.vstack((zeros_row,velKO_ASC_overlap)) # Velocity obtained by finite differences
            locVelKO_ASC_overlap = rKO_ASC_overlap.apply(velKO_ASC_overlap, inverse=True)

            linVelKO_ASC_fb_overlap = dfObservers_overlap[['KO_ASC_velW_vx', 'KO_ASC_velW_vy', 'KO_ASC_velW_vz']].to_numpy() # estimated linear velocity
            angVelKO_ASC_fb_overlap = dfObservers_overlap[['KO_ASC_velW_wx', 'KO_ASC_velW_wy', 'KO_ASC_velW_wz']].to_numpy() # estimated angular velocity
            linVelKO_ASC_imu_overlap = linVelKO_ASC_fb_overlap + np.cross(angVelKO_ASC_fb_overlap, rKO_ASC_overlap.apply(posFbImu_overlap)) + rKO_ASC_overlap.apply(linVelFbImu_overlap)

            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_ASC_overlap[:,0], mode='lines', name='locVelKO_ASC_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_ASC_overlap[:,1], mode='lines', name='locVelKO_ASC_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_ASC_overlap[:,2], mode='lines', name='locVelKO_ASC_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_ASC_imu_overlap[:,0], mode='lines', name='linVel_IMU__KO_ASC_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_ASC_imu_overlap[:,1], mode='lines', name='linVel_IMU_KO_ASC_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_ASC_imu_overlap[:,2], mode='lines', name='linVel_IMU_KO_ASC_z'))

            rmse_values['KO_ASC'] = computeRMSE(locVelMocap_overlap, locVelKO_ASC_overlap, "KO_ASC")
            index_labels.append('KO_ASC')
            if(withHartley):
                relative_errors['KO_ASC'] = compute_relative_error(rmse_values['KO_ASC'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['KO_ASC'], relative_errors['KO_ASC']]))
            else:
                data.append(rmse_values['KO_ASC'])

            rWorldImuKO_ASC_overlap = rKO_ASC_overlap * rImuFb_overlap.inv()
            locVelKO_ASC_imu_estim = rWorldImuKO_ASC_overlap.apply(linVelKO_ASC_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelKO_ASC_overlap[:, 0], 'y': locVelKO_ASC_overlap[:, 1], 'z': locVelKO_ASC_overlap[:, 2]}
            d['estimate'] = {'x': locVelKO_ASC_imu_estim[:, 0], 'y': locVelKO_ASC_imu_estim[:, 1], 'z': locVelKO_ASC_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/KO_ASC_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)


        if(withKO_Disabled):
            velKO_Disabled_overlap = np.diff(posKO_Disabled_overlap, axis=0)/timeStep_s
            velKO_Disabled_overlap = np.vstack((zeros_row,velKO_Disabled_overlap)) # Velocity obtained by finite differences
            locVelKO_Disabled_overlap = rKO_Disabled_overlap.apply(velKO_Disabled_overlap, inverse=True)

            linVelKO_Disabled_fb_overlap = dfObservers_overlap[['KO_Disabled_velW_vx', 'KO_Disabled_velW_vy', 'KO_Disabled_velW_vz']].to_numpy() # estimated linear velocity
            angVelKO_Disabled_fb_overlap = dfObservers_overlap[['KO_Disabled_velW_wx', 'KO_Disabled_velW_wy', 'KO_Disabled_velW_wz']].to_numpy() # estimated angular velocity
            linVelKO_Disabled_imu_overlap = linVelKO_Disabled_fb_overlap + np.cross(angVelKO_Disabled_fb_overlap, rKO_Disabled_overlap.apply(posFbImu_overlap)) + rKO_Disabled_overlap.apply(linVelFbImu_overlap)

            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_Disabled_overlap[:,0], mode='lines', name='locVelKO_Disabled_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_Disabled_overlap[:,1], mode='lines', name='locVelKO_Disabled_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelKO_Disabled_overlap[:,2], mode='lines', name='locVelKO_Disabled_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_Disabled_imu_overlap[:,0], mode='lines', name='linVel_IMU__KO_Disabled_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_Disabled_imu_overlap[:,1], mode='lines', name='linVel_IMU_KO_Disabled_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelKO_Disabled_imu_overlap[:,2], mode='lines', name='linVel_IMU_KO_Disabled_z'))

            rmse_values['KO_Disabled'] = computeRMSE(locVelMocap_overlap, locVelKO_Disabled_overlap, "KO_Disabled")
            index_labels.append('KO_Disabled')
            if(withHartley):
                relative_errors['KO_Disabled'] = compute_relative_error(rmse_values['KO_Disabled'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['KO_Disabled'], relative_errors['KO_Disabled']]))
            else:
                data.append(rmse_values['KO_Disabled'])

            rWorldImuKO_Disabled_overlap = rKO_Disabled_overlap * rImuFb_overlap.inv()
            locVelKO_Disabled_imu_estim = rWorldImuKO_Disabled_overlap.apply(linVelKO_Disabled_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelKO_Disabled_overlap[:, 0], 'y': locVelKO_Disabled_overlap[:, 1], 'z': locVelKO_Disabled_overlap[:, 2]}
            d['estimate'] = {'x': locVelKO_Disabled_imu_estim[:, 0], 'y': locVelKO_Disabled_imu_estim[:, 1], 'z': locVelKO_Disabled_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/KO_Disabled_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)

        if(withVanyte):
            velVanyte_overlap = np.diff(posVanyte_overlap, axis=0)/timeStep_s
            velVanyte_overlap = np.vstack((zeros_row,velVanyte_overlap))
            locVelVanyte_overlap = rVanyte_overlap.apply(velVanyte_overlap, inverse=True)

            linVelVanyte_fb_overlap = dfObservers_overlap[['Vanyte_vel_vx', 'Vanyte_vel_vy', 'Vanyte_vel_vz']].to_numpy() # estimated linear velocity
            angVelVanyte_fb_overlap = dfObservers_overlap[['Vanyte_vel_wx', 'Vanyte_vel_wy', 'Vanyte_vel_wz']].to_numpy() # estimated angular velocity
            linVelVanyte_imu_overlap = linVelVanyte_fb_overlap + np.cross(angVelVanyte_fb_overlap, rVanyte_overlap.apply(posFbImu_overlap)) + rVanyte_overlap.apply(linVelFbImu_overlap)
            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelVanyte_overlap[:,0], mode='lines', name='locVelVanyte_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelVanyte_overlap[:,1], mode='lines', name='locVelVanyte_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelVanyte_overlap[:,2], mode='lines', name='locVelVanyte_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelVanyte_imu_overlap[:,0], mode='lines', name='linVel_IMU__Vanyte_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelVanyte_imu_overlap[:,1], mode='lines', name='linVel_IMU_Vanyte_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelVanyte_imu_overlap[:,2], mode='lines', name='linVel_IMU_Vanyte_z'))
            rmse_values['Vanyte'] = computeRMSE(locVelMocap_overlap, locVelVanyte_overlap, "Vanyte")
            index_labels.append('Vanyte')
            if(withHartley):
                relative_errors['Vanyte'] = compute_relative_error(rmse_values['Vanyte'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['Vanyte'], relative_errors['Vanyte']]))
            else:
                data.append(rmse_values['Vanyte'])

            rWorldImuVanyte_overlap = rVanyte_overlap * rImuFb_overlap.inv()
            locVelVanyte_imu_estim = rWorldImuVanyte_overlap.apply(linVelVanyte_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelVanyte_overlap[:, 0], 'y': locVelVanyte_overlap[:, 1], 'z': locVelVanyte_overlap[:, 2]}
            d['estimate'] = {'x': locVelVanyte_imu_estim[:, 0], 'y': locVelVanyte_imu_estim[:, 1], 'z': locVelVanyte_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/Vanyte_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)

        if(withTilt):
            velTilt_overlap = np.diff(posTilt_overlap, axis=0)/timeStep_s
            velTilt_overlap = np.vstack((zeros_row,velTilt_overlap))
            locVelTilt_overlap = rTilt_overlap.apply(velTilt_overlap, inverse=True) 

            linVelTilt_fb_overlap = dfObservers_overlap[['Tilt_vel_vx', 'Tilt_vel_vy', 'Tilt_vel_vz']].to_numpy() # estimated linear velocity
            angVelTilt_fb_overlap = dfObservers_overlap[['Tilt_vel_wx', 'Tilt_vel_wy', 'Tilt_vel_wz']].to_numpy() # estimated angular velocity
            linVelTilt_imu_overlap = linVelTilt_fb_overlap + np.cross(angVelTilt_fb_overlap, rTilt_overlap.apply(posFbImu_overlap)) + rTilt_overlap.apply(linVelFbImu_overlap)
            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelTilt_overlap[:,0], mode='lines', name='locVelTilt_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelTilt_overlap[:,1], mode='lines', name='locVelTilt_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelTilt_overlap[:,2], mode='lines', name='locVelTilt_z'))

                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelTilt_imu_overlap[:,0], mode='lines', name='linVel_IMU__Tilt_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelTilt_imu_overlap[:,1], mode='lines', name='linVel_IMU_Tilt_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=linVelTilt_imu_overlap[:,2], mode='lines', name='linVel_IMU_Tilt_z'))
            rmse_values['Tilt'] = computeRMSE(locVelMocap_overlap, locVelTilt_overlap, "Tilt")
            index_labels.append('Tilt')
            if(withHartley):
                relative_errors['Tilt'] = compute_relative_error(rmse_values['Tilt'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['Tilt'], relative_errors['Tilt']]))
            else:
                data.append(rmse_values['Tilt'])

            rWorldImuTilt_overlap = rTilt_overlap * rImuFb_overlap.inv()
            locVelTilt_imu_estim = rWorldImuTilt_overlap.apply(linVelTilt_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelTilt_overlap[:, 0], 'y': locVelTilt_overlap[:, 1], 'z': locVelTilt_overlap[:, 2]}
            d['estimate'] = {'x': locVelTilt_imu_estim[:, 0], 'y': locVelTilt_imu_estim[:, 1], 'z': locVelTilt_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/Tilt_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)

        if(withController):
            velController_overlap = np.diff(posController_overlap, axis=0)/timeStep_s
            velController_overlap = np.vstack((zeros_row,velController_overlap))
            locVelController_overlap = rController_overlap.apply(velController_overlap, inverse=True)
            if(displayLogs):
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelController_overlap[:,0], mode='lines', name='locVelController_x'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelController_overlap[:,1], mode='lines', name='locVelController_y'))
                figLocLinVels.add_trace(go.Scatter(x=dfObservers_overlap["t"], y=locVelController_overlap[:,2], mode='lines', name='locVelController_z'))
            rmse_values['Controller'] = computeRMSE(locVelMocap_overlap, locVelController_overlap, "Controller")
            index_labels.append('Controller')
            if(withHartley):
                relative_errors['Controller'] = compute_relative_error(rmse_values['Controller'], rmse_values['Hartley'])
                data.append(np.concatenate([rmse_values['Controller'], relative_errors['Controller']]))
            else:
                data.append(rmse_values['Controller'])


            posController_imu_overlap = posController_overlap + rController_overlap.apply(posFbImu_overlap)
            velController_imu_overlap = np.diff(posController_imu_overlap, axis=0)/timeStep_s
            velController_imu_overlap = np.vstack((zeros_row,velController_imu_overlap))

            rWorldImuController_overlap = rController_overlap * rImuFb_overlap.inv()
            locVelController_imu_estim = rWorldImuController_overlap.apply(velController_imu_overlap, inverse=True)
            d = {'llve': {}, 'estimate': {}}
            d['llve'] = {'x': locVelController_overlap[:, 0], 'y': locVelController_overlap[:, 1], 'z': locVelController_overlap[:, 2]}
            d['estimate'] = {'x': locVelController_imu_estim[:, 0], 'y': locVelController_imu_estim[:, 1], 'z': locVelController_imu_estim[:, 2]}
            with open(f'{path_to_project}/output_data/Controller_loc_vel.pickle', 'wb') as f:
                pickle.dump(d, f)
        

        if(displayLogs):
            figLocLinVels.show()


        df = pd.DataFrame(data, index=index_labels, columns=index)
