from numpy import *
from pylab import *
from scipy.sparse import *


class LRAProblem(object):
	'''
	This class defines the 2D LRA neutron diffusion benchmark problem,
	including the material properties and geometry.
	'''

	def __init__(self, num_mesh_x=5, num_mesh_y=5):
		'''
		Initialize LRA geometry and materials
		'''

		# Define the boundaries of the geometry [cm]		
		self._xmin = 0.;
		self._xmax = 165.;
		self._ymin = 0.;
		self._ymax = 165.;

    	# number of mesh per coarse grid cell in LRA problem 
		self._num_mesh_x = num_mesh_x
		self._num_mesh_y = num_mesh_y

		# mesh spacing - each LRA coarse grid cell is 5cm x 5cm
		self._dx = 15. / self._num_mesh_x
		self._dy = 15. / self._num_mesh_y

		# number of mesh cells in x,y dimension for entire LRA geometry
		self._num_x_cells = self._num_mesh_x * 11
		self._num_y_cells = self._num_mesh_y * 11

		print 'num x = %d, num y = %d' % (self._num_x_cells, self._num_y_cells)

    	# Create a numpy array for materials ids
		self._material_ids = array([[5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
									   [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
									   [3, 3, 3, 3, 3, 3, 3, 5, 5, 5, 5],
									   [3, 3, 3, 3, 3, 3, 3, 4, 5, 5, 5],
									   [2, 1, 1, 1, 1, 2, 2, 3, 3, 5, 5],
									   [2, 1, 1, 1, 1, 2, 2, 3, 3, 5, 5],
									   [1, 1, 1, 1, 1, 1, 1, 3, 3, 5, 5],
									   [1, 1, 1, 1, 1, 1, 1, 3, 3, 5, 5],
									   [1, 1, 1, 1, 1, 1, 1, 3, 3, 5, 5],
									   [1, 1, 1, 1, 1, 1, 1, 3, 3, 5, 5],
									   [2, 1, 1, 1, 1, 2, 2, 3, 3, 5, 5]])

    	# Dictionary with keys (material ids) to diffusion coefficients
		self._D = {1: [1.255, 0.211], 
         		   2: [1.268, 0.1902],
         		   3: [1.259, 0.2091],
         		   4: [1.259, 0.2091],
         		   5: [1.257, 0.1592]}

    	# Dictionary with keys (material ids) to absorption cross-sections
		self._SigmaA = {1: [0.008252, 0.1003], 
                        2: [0.007181, 0.07047],
              			3: [0.008002, 0.08344],
              			4: [0.008002, 0.073324],
              			5: [0.0006034, 0.01911]}

    	# Dictionary with keys (material ids) to fission cross-sections
		self._NuSigmaF = {1: [0.004602, 0.1091], 
                		  2: [0.004609, 0.08675],
                		  3: [0.004663, 0.1021],
                		  4: [0.004663, 0.1021],
               		 	  5: [0., 0.]}

    	# Dictionary with keys (material ids) to group 2 to 1 scattering           
    	# cross-sections
		self._SigmaS21 = {1: 0.02533, 
                		  2: 0.02767,
                		  3: 0.02617,
                		  4: 0.02617,
                		  5: 0.04754}

		# Geometric Buckling
		self._Bsquared = 1E-4

    	# Array with the material id for each fine mesh cell
		self._materials = zeros([self._num_x_cells, self._num_y_cells], float)
		for i in range(self._num_x_cells):
			for j in range(self._num_y_cells):
				self._materials[j,i] = self._material_ids[j  / \
										self._num_mesh_x][i / self._num_mesh_y]

		# Sparse destruction matrix used for solver (initialized empty)
		self.setupMFMatrices()


	def setupMFMatrices(self):
		'''
		Construct the destruction (M) and production (F) matrices
		in the neutron diffusion eigenvalue equation for the LRA 
		problem with a particular mesh size.
		'''

		# Create arrays for each of the diagonals of the 
		# production and destruction matrices
		size = 2 * self._num_x_cells * self._num_y_cells
		M_diag = zeros(size)
		M_udiag = zeros(size)
		M_2udiag = zeros(size)
		M_ldiag = zeros(size)
		M_2ldiag = zeros(size)
		M_3ldiag = zeros(size)
		F_diag1 = zeros(size)
		F_diag2 = zeros(size)
		
		# Loop over all cells in the mesh
		for i in range(size):

			# energy group 1
			if i < size / 2:
				x = i % self._num_x_cells
				y = i / self._num_y_cells
				mat_id = self._materials[y,x]

				# 2D lower - leakage from top cell
				if y > 0:
					M_2ldiag[i-self._num_x_cells] = -self._dx * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y-1,x]][0], self._dy)

				# lower - leakage from left cell
				if x > 0:
					M_ldiag[i-1] = -self._dy * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y,x-1]][0], self._dx)

				# 2D upper - leakage from bottom cell
				if y < self._num_y_cells-1:
					M_2udiag[i+self._num_x_cells] = -self._dx * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y+1,x]][0], self._dy)

				# upper - leakage from right cell
				if x < self._num_x_cells-1:
					M_udiag[i+1] = -self._dy * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y,x+1]][0], self._dx)

				# diagonal - absorption, downscattering, axial leakage
				M_diag[i] = (self._SigmaA[mat_id][0] + \
							self._D[mat_id][0] * self._Bsquared + \
                            self._SigmaS21[mat_id]) * self._dx * self._dy

				# leakage into cell above
				if y > 0:
					M_diag[i] += self._dx * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y-1,x]][0], self._dy)

				# leakage into cell below
				if y < self._num_y_cells-1:
					M_diag[i] += self._dx * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y+1,x]][0], self._dy)

				# leakage into cell to the left
				if x > 0:
					M_diag[i] += self._dy * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y,x-1]][0], self._dy)

				# leakage into cell to the right
				if x < self._num_x_cells-1:
					M_diag[i] += self._dy * \
								self.computeDCouple(self._D[mat_id][0], \
								self._D[self._materials[y,x+1]][0], self._dy)

				# leakage into vacuum for cells at top edge of the geometry
				if (y == 0):
					M_diag[i] += (2.0 * self._D[mat_id][0] / self._dx) * \
						(1.0 / (1.0 + (4.0 *  self._D[mat_id][0] / self._dx)))

				# leakage into vacuum for cells at right edge of the geometry
				if (x == self._num_x_cells-1):
					M_diag[i] += (2.0 * self._D[mat_id][0] / self._dy) * \
						(1.0 / (1.0 + (4.0 *  self._D[mat_id][0] / self._dx)))

				# fission production
				F_diag1[i] = self._NuSigmaF[mat_id][0]

				# fission production
				F_diag2[i+size/2] = self._NuSigmaF[mat_id][1]

			# energy group 2
			else:
				x = (i-(size/2)) % self._num_x_cells
				y = (i-(size/2)) / self._num_y_cells
				mat_id = self._materials[y,x]

				# Group 1 scattering into group 2
				M_3ldiag[i-size/2] = -self._SigmaS21[mat_id] * \
												self._dx * self._dy

				# 2self._D lower - leakage from top cell
				if y > 0:
					M_2ldiag[i-self._num_x_cells] = -self._dx * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y-1,x]][1], self._dy)

				# lower - leakage from left cell
				if x > 0:
					M_ldiag[i-1] = -self._dy * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y,x-1]][1], self._dx)

				# 2self._D upper - leakage from bottom cell
				if y < self._num_y_cells-1:
					M_2udiag[i+self._num_x_cells] = -self._dx * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y+1,x]][1], self._dy)

				# upper - leakage from right cell
				if x < self._num_x_cells-1:
					M_udiag[i+1] = -self._dy * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y,x+1]][1], self._dx)

				# diagonal - absorption, downscattering, axial leakage
				M_diag[i] = (self._SigmaA[mat_id][1]  + \
							self._D[mat_id][1] * self._Bsquared) * \
											self._dx * self._dy

				# leakage into cell above
				if y > 0:
					M_diag[i] += self._dx * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y-1,x]][1], self._dy)

				# leakage into cell below
				if y < self._num_y_cells-1:
					M_diag[i] += self._dx * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y+1,x]][1], self._dy)

				# leakage into cell to the left
				if x > 0:
					M_diag[i] += self._dy * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y,x-1]][1], self._dy)

				# leakage into cell to the right
				if x < self._num_x_cells-1:
					M_diag[i] += self._dy * \
								self.computeDCouple(self._D[mat_id][1], \
								self._D[self._materials[y,x+1]][1], self._dy)

				# leakage into vacuum for cells at top edge of the geometry
				if (y == 0):
					M_diag[i] += (2.0 * self._D[mat_id][0] / self._dx) * \
						(1.0 / (1.0 + (4.0 *  self._D[mat_id][1] / self._dx)))

				# leakage into vacuum for cells at right edge of the geometry
				if (x == self._num_x_cells-1):
					M_diag[i] += (2.0 * self._D[mat_id][0] / self._dy) * \
						(1.0 / (1.0 + (4.0 *  self._D[mat_id][1] / self._dy)))


		# Construct sparse diagonal matrices
		self._M = dia_matrix(([M_diag, M_udiag, M_2udiag, M_ldiag, M_2ldiag, 
							M_3ldiag], [0, 1, self._num_x_cells, -1, \
							-self._num_x_cells, -size/2]), shape=(size, size))
		self._F = dia_matrix(([F_diag1, F_diag2], [0, size/2]), \
												shape=(size, size))


	def plotMaterials(self):
		'''
		Plot a coarse 2D grid of the materials in the LRA problem
		'''	
		
		mpl.figure()
		pcolor(linspace(self._xmin, self._xmax, 12), \
				linspace(self._ymin, self._ymax, 12), \
				self._material_ids.T, edgecolors='k', linewidths=1)
		axis([0, 165, 0, 165])
		title('2D LRA Benchmark Materials')
		show()


	def plotMesh(self):
		'''
		Plot the fine 2D mesh used to solve the LRA problem
		'''	

		figure()
		pcolor(linspace(0, 165, self._num_x_cells), \
				linspace(0, 165, self._num_y_cells), \
				self._materials.T, edgecolors='k', linewidths=0.25)
		axis([0, 165, 0, 165])
		title('2D LRA Benchmark Mesh')
		show()


	def spyMF(self):
		'''
		Display nonzeros for production (M) and destruction matrices (F)
		'''

		fig = figure()
		fig.add_subplot(121)		
		spy(self._M)
		fig.add_subplot(122)		
		spy(self._F)
		show()


	def computeDCouple(self, D1, D2, delta):
		'''
		Compute the diffusion coefficient coupling two adjacent cells
		'''
		return (2.0 * D1 * D1) / (delta * (D1 + D2))


	def computeF(self, x):
		'''
		Compute the residual vector for JFNK
		'''

		m = x.size
		phi = x[:m-1]
		lamb = x[m-1]
		print 'lamb = ' + str(lamb)

		# Allocate space for F
		F = ones((m, 1))
	
		# M - lambda * F * phi constraint
		F[:m-1] = self._M * phi - (1. / lamb[0]) * self._F * phi

		# Flux normalization constraint
		F[m-1] = -0.5 * vdot(phi, phi) + 0.5

		return F


	def plotPhi(self, phi):
		'''
		Generate a 2D color plot of the fast and thermal flux from a 1D ndarray
		'''

		# Assumes phi is a numpy column vector

		# Plot the thermal and fast flux and convergence rate
		fig = figure()
		phi_g1 = reshape(phi[0:self._num_y_cells * self._num_x_cells], \
							(-self._num_y_cells, self._num_y_cells), order='A')
		phi_g2 = reshape(phi[self._num_y_cells * self._num_x_cells:], \
							(-self._num_y_cells, self._num_y_cells), order='A')
		phi_g1 = flipud(phi_g1)
		phi_g2 = flipud(phi_g2)
	
		fig.add_subplot(121)
		pcolor(linspace(0, 165, self._num_x_cells), \
								linspace(0, 165, self._num_y_cells), phi_g1)
		colorbar()	
		axis([0, 165, 0, 165])
		title('Group 1 (Fast) Flux')
	
		fig.add_subplot(122)
		pcolor(linspace(0, 165, self._num_x_cells), \
								linspace(0, 165, self._num_y_cells), phi_g2)
		colorbar()
		axis([0, 165, 0, 165])
		title('Group 2 (Thermal) Flux')

		show()


	def computeAnalyticJacobian(self, x):

		m = x.shape[0]
		phi = x[:m-1]
		lamb = x[m-1]

		J = lil_matrix((m,m))

		# Construct temporary blocks for Jacobian
		a = self._M - lamb[0] * self._F
		b = -0.5 * phi.T
		c = -self._F * phi
		c = vstack([c, zeros(1)])

		# Build Jacobian using scipy's sparse matrix stacking operators
		J = vstack([a, b])
		J = hstack([J, c])

		return J


	def computeAnalyticJacobVecProd(self, x, y):

		m = x.shape[0]
		phi = x[:m-1]
		lamb = x[m-1]

		J = lil_matrix((m,m))

		# Construct temporary blocks for Jacobian
		a = self._M - lamb[0] * self._F
		b = phi.T
		c = -self._F * phi
		c = vstack([c, zeros(1)])

		# Build Jacobian using scipy's sparse matrix stacking operators
		J = vstack([a, b])
		J = hstack([J, c])

		return J * y


	def computeFDJacobVecProd(self, x, y):

		phi = x[:x.size-2]
		lamb = x[x.size-1]		
		y = resize(y, [y.size, 1])

		b = 1E-8

		epsilon = b * sum(x) / (y.size * norm(y))
		
		# Approximate Jacobian matrix vector multiplication
		tmp1 = self.computeF(x + (epsilon * y))
#		print 'compute tmp1'
		tmp2 = self.computeF(x)
#		print 'compute tmp2'
		Jy = (tmp1 - tmp2) / epsilon

		return Jy




		# Full weighting stencils for multigrid
		self._R_interior = np.array([[0.25, 0.5, 0.25], \
									 [0.5, 1.0, 0.5], \
									 [0.25, 0.5, 0.25]])
		self._R_interior *= (1 / 4.)

		self._R_tl = np.array([[1., 0.5], \
							   [0.5, 0.25]])
		self._R_tl *= (1. / 2.25)

		self._R_tr = np.array([[0.5, 1.], \
							   [0.25, .5]])
		self._R_tr *= (1. / 2.25)

		self._R_bl = np.array([[0.5, 0.25], \
							   [1., 0.5]])
		self._R_bl *= (1. / 2.25)

		self._R_br = np.array([[0.25, 0.5], \
							   [0.5, 1.]])
		self._R_br *= (1. / 2.25)

		self._R_top = np.array([[0.5, 0.25], \
								[1., 0.5], \
								[0.5, 0.25]])
		self._R_top *= (1. / 3.)		

		self._R_bottom = np.array([[0.5, 0.25], \
								   [0.5, 1.], \
								   [0.25, 0.5]])
		self._R_bottom *= (1. / 3.)



	def restrict(self, x):
		'''
		This restriction operator requires the number of mesh to be odd
		'''

		x = np.asarray(x)

		mesh_size = int(sqrt(x.size))
		new_mesh_size = int(ceil(mesh_size / 2.))

		print 'x.size = %d, mesh_size = %d, new_mesh_size = %d' % (x.size, mesh_size, new_mesh_size)
		
		# Reshape x into 2D arrays corresponding to the geometric mesh
		x = np.reshape(x, [mesh_size, mesh_size])

		# Allocate memory for the restricted x 
		x_new = np.zeros((new_mesh_size, new_mesh_size))

		# Restrict the x and b vectors
		for i in range(new_mesh_size):
			for j in range(new_mesh_size):
				print 'i = %d, j = %d' % (i,j)
				# top left corner
				if (i is 0 and j is 0):
					x_new[i,j] = sum(np.dot(self._R_tl, x[i*2:i*2+2,j*2:j*2+2]))
				# top right corner
				elif (i is 0 and j is new_mesh_size-1):
					x_new[i,j] = sum(np.dot(self._R_tr, x[i*2:i*2+2, j*2:j*2+1]))
				# top row but not a corner
				elif (i is 0):
					x_new[i,j] = sum(np.dot(self._R_top, x[i*2:i*2+2, j*2-1:j*2+2]))
				# bottom left corner
				elif (i is new_mesh_size-1 and j is 0):
					print 'R_bl.shape = ' + str(self._R_bl.shape) + 'x[i*2-1:i*2, j*2:j*2+2].shape = ' + str(x[i*2-1:i*2+1, j*2:j*2+2].shape)
					x_new[i,j] = sum(np.dot(self._R_bl, x[i*2-1:i*2+1, j*2:j*2+2]))
				# bottom right corner
				elif (i is new_mesh_size-1 and j is new_mesh_size-1):
					x_new[i,j] = sum(np.dot(self._R_br, x[i*2:i*2+1, j*2:j*2+1]))
				# bottom row but not a corner
				elif (i is new_mesh_size-1):
					x_new[i,j] = sum(np.dot(self._R_bottom, x[i*2:i*2+1, j*2-1:j*2+1]))
				# interior cell
				else:
					x_new[i,j] = sum(np.dot(self._R_interior, x[i*2-1:i*2+2, j*2-1:j*2+1]))


#				print 'i = %d, j = %d' % (i, j)
#				x_new[i,j] = sum(np.dot(self._R, x[i*2:i*2+3, j*2:j*2+3]))

		# Reshape x and b back into 1D arrays
		x_new = np.ravel(x_new)

		print 'x_new.size = %d, x_old.size = %d' % (x_new.size, x.size)

		return x_new



	def restrictAxb(self, A, x, b, m):
		'''

		'''

		#######################################################################
		#								Restrict M							  #
		#######################################################################

		# Extract the diagonals for M and F
		# Pad with zeros at front for superdiagonals / back for subdiagonals
		A = A.todense()
		size = A.shape[0]

		M_diag = [A[i,i] for i in range(size)]

		M_udiag = zeros(size)
		M_udiag[1:size] = [A[i,i+1] for i in range(size-1)]
		M_udiag = np.asarray(M_udiag)

		M_2udiag = zeros(size)
		M_2udiag[m:size] = [A[i,i+m] for i in range(size-m)]
		M_2udiag = np.asarray(M_2udiag)

		M_ldiag = zeros(size)
		M_ldiag[:size-1] = [A[i+1,i] for i in range(size-1)]
		M_ldiag = np.asarray(M_ldiag)

		M_2ldiag = zeros(size)
		M_2ldiag[:size-m] = [A[i+m,i] for i in range(size-m)]
		M_2ldiag = np.asarray(M_2ldiag)

		M_3ldiag = zeros(size)
		M_3ldiag[:size/2] = [A[i+size/2,i] for i in range(size/2)]
		M_3ldiag = np.asarray(M_3ldiag)


		# Restrict each energy group of each subdiagonal
		print 'size = %d' % (size)
		M_diag_egroup1_new = self.restrict(M_diag[:size/2])
		M_diag_egroup2_new = self.restrict(M_diag[size/2:])
		M_diag_new = np.append(M_diag_egroup1_new, M_diag_egroup2_new)

		M_udiag_egroup1_new = self.restrict(M_udiag[:size/2.])
		M_udiag_egroup2_new = self.restrict(M_udiag[size/2.:])
		M_udiag_new = np.append(M_udiag_egroup1_new, M_udiag_egroup2_new)

		M_2udiag_egroup1_new = self.restrict(M_2udiag[:size/2.])
		M_2udiag_egroup2_new = self.restrict(M_2udiag[size/2.:])
		M_2udiag_new = np.append(M_2udiag_egroup1_new, M_2udiag_egroup2_new)

		M_ldiag_egroup1_new = self.restrict(M_ldiag[:size/2.])
		M_ldiag_egroup2_new = self.restrict(M_ldiag[size/2.:])
		M_ldiag_new = np.append(M_ldiag_egroup1_new, M_ldiag_egroup2_new)

		M_2ldiag_egroup1_new = self.restrict(M_2ldiag[:size/2.])
		M_2ldiag_egroup2_new = self.restrict(M_2ldiag[size/2.:])
		M_2ldiag_new = np.append(M_2ldiag_egroup1_new, M_2ldiag_egroup2_new)

		M_3ldiag_egroup1_new = self.restrict(M_3ldiag[:size/2.])
		M_3ldiag_egroup2_new = self.restrict(M_3ldiag[size/2.:])
		M_3ldiag_new = np.append(M_3ldiag_egroup1_new, M_3ldiag_egroup2_new)


		# Construct the restricted A matrix
		A_new = dia_matrix(([M_diag_new, M_udiag_new, M_2udiag_new, 
							   M_ldiag_new, M_2ldiag_new, M_3ldiag_new], 
							   [0, 1, m/2., -1, -m/2., -size/4]), \
								shape=(size/4., size/4.))

				
		#######################################################################
		#							Restrict x and b						  #
		#######################################################################
		# Reshape x and b into 2D arrays corresponding to the geometric mesh
		# with separate arrays for each energy group
		print 'x.size = %d, x.size/2 = %d' % (x.size, x.size/2)
		print 'x[:(x.size/2)].shape = ' + str(x[:(x.size/2)].shape)
		x_egroup1 = np.asarray(x[:(x.size/2)])
		x_egroup2 = x[x.size/2:]
		b_egroup1 = b[:x.size/2]
		b_egroup2 = b[x.size/2:]

		# Restrict each energy group of x and b
		x_egroup1_new = self.restrict(x_egroup1)
		x_egroup2_new = self.restrict(x_egroup2)
		b_egroup1_new = self.restrict(b_egroup1)
		b_egroup2_new = self.restrict(b_egroup2)

		print 'x_egroup1.size = %d, x_egroup1_new.size = %d' % (x_egroup1.size, x_egroup1_new.size)
		print 'x_egroup2.size = %d, x_egroup2_new.size = %d' % (x_egroup2.size, x_egroup2_new.size)

		# Concatenate restricted x and b energy groups
		x_new = np.append(x_egroup1_new, x_egroup2_new)
		b_new = np.append(b_egroup1_new, b_egroup2_new)

		print 'x_new.size = ' + str(x_new.size)

		return A_new, x_new, b_new



	def prolongation(b, x):
		'''
		'''

		return

		# 
		m_old = sqrt(x.size)
		m_new = m_old

		# Reshape x and b into 2D arrays corresponding to the geometric mesh
		x = np.reshape(x, [sqrt(m_old), sqrt(m_old)])
		b = np.reshape(b, [sqrt(m_old), sqrt(m_old)])

		# Allocate memory for the restricted x
		x_new = np.array((sqrt(m_new), sqrt(m_new)))
		b_new = np.array((sqrt(m_new), sqrt(m_new)))

		# Restrict the x and b vectors
		for i in range(sqrt(m_new)):
			for j in range(sqrt(m_new)):
				x_new[i,j] = self._R * x[i*2:i*2+2, j*2:j*2+2]
				b_new[i,j] = self._R * b[i*2:i*2+2, j*2:j*2+2]

		return x_new, b_new
		
