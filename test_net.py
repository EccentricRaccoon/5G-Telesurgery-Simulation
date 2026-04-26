from network import Matlab5GNetwork

net = Matlab5GNetwork()
print("Using MATLAB:", net.using_matlab)
net.set_technology('4g')
net.set_snr(15)
print("4G Metrics at 15dB:", net.get_current_metrics())
net.set_technology('5g')
net.set_snr(15)
print("5G Metrics at 15dB:", net.get_current_metrics())
